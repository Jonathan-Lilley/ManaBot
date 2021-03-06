'''                             COD to TXT converter                            '''
'''
        This file converts .cod files to .txt files; .cod files are an .xml format file
        Specifically, it will take a filepath for a .cod and write a new file as a .txt with the same name
'''
import os, shutil, asyncio, requests
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from helpers import stripExt, simplifyString

NUMERALS = {str(i) for i in range(0, 9)}

class DeckMgr:
    def __init__(self, path_to_bot, deckDirs, CardManager):
        self.ptb = path_to_bot
        self.dirs = deckDirs
        self.cm = CardManager

    # Generic command handler. It processing attachments and/or commands as needed
    def handle(self,attached=None,cmd=None):
        if cmd and not attached:
            if cmd == "!cleardecks":
                self._cleardecks()
        if attached:
            # Get file data stuff; name, url, raw data
            fullname = attached[0]
            furl = attached[1]
            r = requests.get(furl)
            # Save the file data
            srcpath = self.ptb+"/toparse/"+fullname
            open(srcpath, 'wb').write(r.content)
            # Convert!
            decks = self._convert(fullname)
            # Checks for command and throws error if wrong cmd
            if cmd:
                if cmd == "!checkban":
                    return [self._checkbanned(d[0]) for d in decks]
                elif cmd == "!analyze":
                    return [self._analyze(d[0]) for d in decks]
                else:
                    return [f"Command {cmd} not found. Did you mean '!checkban' or '!analyze'?"]
            # otherwise just spit out the decklists as txt's
            else:
                return decks

    ###############################################################
    ###############################################################
    ###############################################################

    # Convert overall

    # Main convert function
    def _convert(self, f):
        # parse name and get paths
        name, ext = stripExt(f)
        srcpath = self.ptb + "/toparse/"
        textpath = self.ptb + "/txts/"
    
        # flist is a list of tuples of (path, filename) so that it uploads the file and a palatable name for it
        # Collect it dynamically
        if ext in ['.cod', '.mwDeck', '.txt']:
            self._convertDeck(srcpath, textpath, name, ext)
            flist = [(textpath + name + '.txt', name + '.txt')]
        elif ext == '.mwDeck':
            flist = []
        elif ext == '.zip':
            flist = self._convertZip(f)
        else:
            flist = [None]
        # return list of file paths
        return flist

    ###############################################################
    ###############################################################
    ###############################################################

    # Convert the zips
    
    # Converts a whole zip by unzipping it, then converting each file within the unzipped dir
    # There may be filename collisions but... that's a later project
    def _convertZip(self, Z):
        zipname, zext = stripExt(Z)
        # mkdir with same name as zip
        subparse = self.ptb + "/toparse/" + zipname
        subtext = self.ptb + "/txts/" + zipname
        # Make sure there aren't any of these dirs, then make them
        # Baseically ensure they exist and are empty
        if os.path.exists(subparse):
            shutil.rmtree(subparse)
        if os.path.exists(subtext):
            shutil.rmtree(subtext)
        os.mkdir(subparse)
        os.mkdir(subtext)
        # extract all to that dir
        with ZipFile(self.ptb + "/toparse/" + Z) as zf:
            zf.extractall(subparse)
        # Convert all the files and collect their paths,names
        flist = []
        return self._convertDir(subparse, subtext, flist)
    
    
    # Converts a directory recursively
    def _convertDir(self, dirpath, textpath, flist):
        for df in os.listdir(dirpath):
            # Recurse if theres a dir
            if os.path.isdir(dirpath + '/' + df):
                flist = self._convertDir(dirpath + '/' + df, textpath, flist)
            # Convert if it's a cod or mwDeck
            else:
                fname, fext = stripExt(df)
                if fext in ['.cod']:
                    self._convertDeck(dirpath + '/', textpath + '/', fname, fext)
                    flist.append((textpath + '/' + fname + '.txt', fname + '.txt'))
                elif fext == '.mwDeck':
                    flist.append("Currently .mwDecks are not supported.")
        # return list of file paths
        return flist

    ###############################################################
    ###############################################################
    ###############################################################

    # Convert individual decks
    
    # Convert a deck
    # Basically goes through each possible extension and runs convert on it
    def _convertDeck(self, srcpath, textpath, name, ext):
        if ext == '.cod':
            cards = self._convertCod(srcpath, name + ext)
        elif ext == '.mwDeck':
            cards = self._convertmwDeck(srcpath + name + ext)
        elif ext == '.txt':
            cards = [line for line in open(srcpath + name + ext)]
        # Just in case, so it doesn't completely crash
        else:
            cards = ['error']
        # Write joined list of cards
        with open(textpath + name + '.txt', 'w') as wf:
            wf.write('\n'.join(cards))


    # Converts a .cod file, which is basically an .xml file
    def _convertCod(self, filepath, namefull):
        fullpath = filepath + namefull
        CODtree = ET.parse(fullpath)  # Get the cod file as an xml tree
        root = CODtree.getroot()  # get root
        cards = []  # initialize cards list
        # Loop through etree
        for child in root:
            if child.tag in ['deckname','comments'] and child.text:
                for t in child.text.split('\n'):
                    cards.append("//"+t)
            # Loop through children of a card zone
            if child.tag == 'zone':
                for c in child:
                    # Get the number of a type of card along with what the card is (e.g. '1 Sol Ring' or '10 Plains')
                    cardline = c.attrib['number'] + " " + c.attrib['name']
                    # If it's sideboarded, add 'SB: '
                    if child.attrib['name'] != 'main':
                        cardline = 'SB: ' + cardline
                    # append to all cards
                    cards.append(cardline)
        # return as list of cards
        return cards

    # Converts .mwDeck, which is basically a .txt file formatted differently from how Cockatrice likes them pasted in
    def _convertmwDeck(self, filepath):
        # Process it like a .txt
        deckFile = [line.strip().split() for line in open(filepath)]
        cards = []
        for line in deckFile:
            # ignores comment lines
            if line[0] == '//':
                continue
            # Adjusts SB lines since its a little different
            elif line[0] == 'SB:':
                cards.append(' '.join(line[:2] + line[3:]))
            else:
                cards.append(' '.join([line[0]] + line[2:]))
        # return as list of cards
        return cards
    
    ###############################################################
    ###############################################################
    ###############################################################

    # Bans

    # Checks cards against a banlist; only works for EDH
    def _checkbanned(self, f):
        # load banlists and decklist
        singlebanned = [line for line in open(self.ptb + "/bans/EDHsingleban.txt")]
        multibanned = [line for line in open(self.ptb + "/bans/EDHmultiban.txt")]
        deck = [line[2:] for line in open(f)]
        # go through sp bans
        sbans = [f"**Deck: {f.split('/')[-1]}**\n*Single player EDH bans:*\n"]
        check = list(set(deck).intersection(set(singlebanned))) # check the intersection of the two things
        if not check:
            sbans.append("None\n")
        else:
            sbans += check
        # repeat with mp
        sbans = ''.join(sbans)
        mbans = ["*Multiplayer EDH bans:*\n"]
        check = list(set(deck).intersection(set(multibanned)))
        if not check:
            mbans.append("None")
        else:
            mbans += check
        mbans = ''.join(mbans)
        allbans = sbans + mbans + '\n\n'
        # return as string
        return allbans

    ###############################################################
    ###############################################################
    ###############################################################

    # analyze

    def _analyze(self, f):
        # get decklist
        deck = [line.strip() for line in open(f)]
        datatypes = ["color","costs","converted","avgcost","lands","cardtypes"]
        data = {dat:dict() for dat in datatypes}
        for c in deck:
            if c[0] not in NUMERALS:
                continue
            card = c.split()[1:]
            card = simplifyString(' '.join(card))
            carddata = self.cm.getRaw(card)
            print(f'\n{c}, {card}\n{carddata}')
            # get color IDs
            if "Color ID" in carddata:
                if "Land" in carddata["Type"]:
                    data["lands"][carddata["Color ID"]] = data["lands"].get(carddata["Color ID"],0)+1
                for col in carddata["Color ID"]:
                    data["color"][col] = data["color"].get(col,0)+1
            else:
                data["color"]["C"] = data["color"].get("C",0)+1
            # get costs
            if "Mana Cost" in carddata:
                for cos in carddata["Mana Cost"]:
                    if "Land" in carddata["Type"]:
                        continue
                    if cos in NUMERALS:
                        data["costs"]["N"] = data["costs"].get("N",0)
                        data["costs"]["N"] = data["costs"]["N"]*10+int(cos)
                    if cos in "{/}":
                        continue
                    else:
                        data["costs"][cos] = data["costs"].get("cos",0)+1
            for cardtype in carddata:
                data["cardtypes"][cardtype] = data["cardtypes"].get(cardtype,0)+1
        data["converted"] = sum([data["costs"][t] for t in data["costs"]])
        data["avgcost"] = data["converted"] - sum([data["lands"][t] for t in data["lands"]])
        for d in data:
            if type(data[d]) == dict:
                data[d] = d + ": " + ', '.join([subd for subd in data[d]])
            else:
                data[d] = d + ": " + str(data[d])
        return '\n'.join([data[d] for d in data])


    def _combineCost(self,mana):
        ttl = 0
        i = 0
        while i < len(mana):
            if i in NUMERALS:
                ttl += int(i)
            elif i != "{":
                while i != "}":
                    i += 1
            ttl += 1
            i += 1
        return ttl




    ###############################################################
    ###############################################################
    ###############################################################

    # clear
    
    # Clears all decks from parse and text dirs
    def _cleardecks(self):
        for p in self.dirs:
            for d in os.listdir(self.ptb+p):
                if os.path.isdir(self.ptb+p+d):
                    shutil.rmtree(self.ptb+p+d)
                else:
                    os.remove(self.ptb+p+d)
    
    async def scheduledClear(self):
        while True:
            await asyncio.sleep(10800)
            self._cleardecks()