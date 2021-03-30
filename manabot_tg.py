import asyncio, os, logging, hashlib

from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor
from PIL import Image
from aiogram.types import InlineQuery, \
    InputTextMessageContent, InlineQueryResultArticle, InlineQueryResultCachedPhoto, InputFile

from readInCards import parseCOD
from loadImages import loadAllImages
from helpers import *

# Load all environment variables
load_dotenv()
TOKEN = os.getenv('TGTOKEN')
path_to_cards = os.getenv('CARDPATH')
path_to_bot = os.getenv('BOTPATH')
imageDirs = os.getenv('IMAGEPATH')
me = os.getenv('KOKITG')

logging.basicConfig(level=logging.DEBUG)
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)


########################################################################################################################
########################################################################################################################
########################################################################################################################

# Get the basic data: pre fix tree and name dictionaries
cards = parseCOD(path_to_cards)
mS(cards)

images, names, loadingErrors = loadAllImages(imageDirs)

print("Number of images loaded:",len(images))

# This specifically stores the file id of cards already sent with the bot so it doesn't have to send the same cards
# over and over and over again
foundCards = {}

########################################################################################################################
########################################################################################################################
########################################################################################################################

# Submit card database errors
async def submitErrors():
    dt = datetime.now().strftime("%d-%m-%Y %H:%M ")
    errs = dt+loadingErrors
    await bot.send_message(me,errs)

# Startup
async def on_startup(d: Dispatcher):
    asyncio.create_task(submitErrors())

########################################################################################################################
########################################################################################################################
########################################################################################################################

# Inline handler
# Man, fuck inline bots, they're such a pain
# This function gets a card based on typing it in on the inline
@dp.inline_handler()
async def postCard(message: InlineQuery):
    # Get cardname simplified
    cardname = simplifyName(message.query)
    # Sets description and pic to None in case the try-except fails
    cardd, cardpic = None, None
    # result ids
    pic_result_id: str = hashlib.md5(cardname.encode()).hexdigest()
    c = cardname+'1'
    text_result_id: str = hashlib.md5(c.encode()).hexdigest()


    # Try-except for the card image
    try:
        # gets the proper name
        if cardname in names:
            propName = names[cardname]
        else:
            propName = findMostSimilar(cards,cardname)
        # gets the path to the proper name
        path = imageDirs + '/' + images[propName] + '/' + propName + '.jpg'
        # Sets an id for sending the message
        result_id: str = hashlib.md5(cardname.encode()).hexdigest()
        # This try tries finding the file id in the dictionary
        try:
            photoid = foundCards[propName]
        # Its except loads or reloads the image if it cant find the file id
        except:
            # Checks to see if the file is too beeg
            sizecheck = Image.open(path)
            if sizecheck.size[0] > 300:
                # and resizes it to 375x500 if so
                resized = sizecheck.resize((300,400), Image.ANTIALIAS)
                path = path_to_bot+'/resizedpics/'+propName+'.jpg' # if it resizes, it gets the new pic's file path
                resized.save(path)
            # That part is specifically to make sure it CAN send the file, cuz if it's too big it wont send
            cardphoto = InputFile(path)
            # Sends the pic to me, saves the file id, and deletes the photo
            pic = await bot.send_photo(me,cardphoto)
            foundCards[propName] = pic.photo[0].file_id
            await bot.delete_message(me,pic.message_id)
            photoid = foundCards[propName]
            # Creates the cardpic variable for sending the file
        # sends cardpic
        cardpic = InlineQueryResultCachedPhoto(id=pic_result_id, photo_file_id=photoid)
    # If all that fails...
    except:
        # Prints a debugging error
        print("Card image not found:",cardname)
        # Creates a card image error to send
        err = "Image for " + cardname + " not found"
        input_content = InputTextMessageContent(err)
        cardpic = InlineQueryResultArticle(
            id=pic_result_id,
            title=f'Can\'t find image for {cardname!r}.',
            input_message_content=input_content,
        )


    # Try-except for card text
    try:
        # This is mostly just so it doesn't crash in the next lines
        # It sets "propName" to cardname, then if it exists in the names dictionary, it replaces it
        similars = findSimilar(cards, cardname)
        if cardname in names:
            propName = names[cardname]
        else:
            propName = similars[0]
        # Gets card data from card prefix tree
        try:
            card = binarySearch(cards, cardname)
            cardData = card.printData()
            # Id for message
            # Creates message content from card data
            input_content = InputTextMessageContent(cardData)
            # Creates result article to send-
            cardd = InlineQueryResultArticle(
                id=text_result_id,
                title=f'Information for {propName!r}',
                input_message_content=input_content,
            )
        except:
            # If it couldn't find the card...
            # Add onto cardData the similar results
            card = binarySearch(cards, propName)
            cardData = card.printData()
            similars = '\n'.join(similars[1:])
            simcards = f'Card not found. Closest match:{propName}\n{cardData}\n\nDid you mean...\n{similars}'
            input_content = InputTextMessageContent(simcards)
            # Use that as the card data
            cardd = InlineQueryResultArticle(
                id=text_result_id,
                title=f'Info not found. Did you mean...\n',
                input_message_content=input_content,
            )
    except:
        print("Card not found. Big error.")

    # Results array
    # Store cardpic and cardd if they are found; if they failed, ignore them
    res = []
    if cardpic != None:
        res.append(cardpic)
    if cardd != None:
        res.append(cardd)

    # Try sending the data, and if it cant just throw an error
    if len(res) > 0:
        await bot.answer_inline_query(message.id, results=res, cache_time=1)
    else:
        print("error\n\n")


if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)