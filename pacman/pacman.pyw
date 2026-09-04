#! /usr/bin/python

# pacman.pyw
# By David Reilly

# Modified by Andy Sommerville, 8 October 2007:
# - Changed hard-coded DOS paths to os.path calls
# - Added constant SCRIPT_PATH (so you don't need to have pacman.pyw and res in your cwd, as long
# -   as those two are in the same directory)
# - Changed text-file reading to accomodate any known EOLn method (\n, \r, or \r\n)
# - I (happily) don't have a Windows box to test this. Blocks marked "WIN???"
# -   should be examined if this doesn't run in Windows
# - Added joystick support (configure by changing JS_* constants)
# - Added a high-score list. Depends on wx for querying the user's name

import pygame, sys, os, random, json
from pygame.locals import *

# WIN???
SCRIPT_PATH=sys.path[0]

# NO_GIF_TILES -- tile numbers which do not correspond to a GIF file
# currently only "23" for the high-score list
NO_GIF_TILES=[23]

NO_WX=0 # if set, the high-score code will not attempt to ask the user his name
USER_NAME="User" # USER_NAME=os.getlogin() # the default user name if wx fails to load or NO_WX

# Joystick defaults - maybe add a Preferences dialog in the future?
JS_DEVNUM=0 # device 0 (pygame joysticks always start at 0). if JS_DEVNUM is not a valid device, will use 0
JS_XAXIS=0 # axis 0 for left/right (default for most joysticks)
JS_YAXIS=1 # axis 1 for up/down (default for most joysticks)
JS_STARTBUTTON=0 # button number to start the game. this is a matter of personal preference, and will vary from device to device

# Must come before pygame.init()
pygame.mixer.pre_init(22050,16,2,512)
JS_STARTBUTTON=0 # button number to start the game. this is a matter of personal preference, and will vary from device to device
pygame.mixer.init()

clock = pygame.time.Clock()
pygame.init()

window = pygame.display.set_mode((1, 1))
pygame.display.set_caption("Pacman")

screen = pygame.display.get_surface()

img_Background = pygame.image.load(os.path.join(SCRIPT_PATH,"res","backgrounds","1.gif")).convert()

snd_pellet = {}
snd_pellet[0] = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","pellet1.wav"))
snd_pellet[1] = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","pellet2.wav"))
snd_powerpellet = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","powerpellet.wav"))
snd_eatgh = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","eatgh2.wav"))
snd_fruitbounce = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","fruitbounce.wav"))
snd_eatfruit = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","eatfruit.wav"))
snd_extralife = pygame.mixer.Sound(os.path.join(SCRIPT_PATH,"res","sounds","extralife.wav"))

ghostcolor = {}
ghostcolor[0] = (255, 0, 0, 255)
ghostcolor[1] = (255, 128, 255, 255)
ghostcolor[2] = (128, 255, 255, 255)
ghostcolor[3] = (255, 128, 0, 255)
ghostcolor[4] = (50, 50, 255, 255) # blue, vulnerable ghost
ghostcolor[5] = (255, 255, 255, 255) # white, flashing ghost

DEFAULT_START_LEVEL = 1
DEFAULT_CURRICULUM = 2

# Source-of-truth event ledger. MaaPacman's worker drains this once after each
# rendered logic frame; no event is inferred from before/after score snapshots.
GAME_EVENT_LEDGER = []
GAME_LOGIC_FRAME = 0


def ResetGameEventLedger():
    global GAME_EVENT_LEDGER, GAME_LOGIC_FRAME
    GAME_EVENT_LEDGER = []
    GAME_LOGIC_FRAME = 0


def BeginGameLogicFrame():
    global GAME_LOGIC_FRAME
    GAME_LOGIC_FRAME += 1
    return GAME_LOGIC_FRAME


def RecordGameEvent(eventType, scoreDelta=0, ghostID=None):
    """Record one concrete gameplay event at its source occurrence point."""
    ghostState = None
    if ghostID is not None and ghostID in ghosts:
        ghostState = {
            1: "normal",
            2: "vulnerable",
            3: "eyes",
            4: "gone",
        }.get(int(ghosts[ghostID].state), "unknown")
    GAME_EVENT_LEDGER.append({
        "frame_index": int(GAME_LOGIC_FRAME),
        "type": str(eventType),
        "pacman_position": [int(player.nearestRow), int(player.nearestCol)],
        "ghost_id": int(ghostID) if ghostID is not None else None,
        "score_delta": int(scoreDelta),
        "ghost_state": ghostState,
        "edible_ticks": int(thisGame.ghostTimer),
    })


def DrainGameEvents():
    """Return and clear source events, annotated with their per-frame total."""
    global GAME_EVENT_LEDGER
    events = GAME_EVENT_LEDGER
    GAME_EVENT_LEDGER = []
    totals = {}
    for event in events:
        frameIndex = event["frame_index"]
        totals[frameIndex] = totals.get(frameIndex, 0) + event["score_delta"]
    for event in events:
        event["frame_score_delta"] = totals[event["frame_index"]]
    return events


def GetGameLogicFrameScoreDelta():
    return sum(
        event["score_delta"]
        for event in GAME_EVENT_LEDGER
        if event["frame_index"] == GAME_LOGIC_FRAME
    )

def ParseStartLevel(argv):
    """Return starting playable level from --start-level N / --level N / -l N."""
    start = DEFAULT_START_LEVEL
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in ("--start-level", "--level", "-l") and i + 1 < len(argv):
            try:
                start = int(argv[i + 1])
            except ValueError:
                pass
            i += 2
            continue
        if arg.startswith("--start-level="):
            try:
                start = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg.startswith("--level="):
            try:
                start = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        i += 1
    if start < 1:
        start = 1
    return start


def ParseCurriculum(argv, environ=None):
    """Return the explicit Level-1 curriculum selected for this process."""
    if environ is None:
        environ = os.environ
    raw = environ.get("MAAPACMAN_CURRICULUM", str(DEFAULT_CURRICULUM))
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--curriculum":
            if i + 1 >= len(argv):
                raise ValueError("--curriculum requires 1 or 2")
            raw = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--curriculum="):
            raw = arg.split("=", 1)[1]
        i += 1
    try:
        curriculum = int(raw)
    except (TypeError, ValueError):
        raise ValueError("curriculum must be 1 or 2")
    if curriculum not in (1, 2):
        raise ValueError("curriculum must be 1 or 2")
    return curriculum


START_LEVEL_NUM = ParseStartLevel(sys.argv)
CURRICULUM_ID = ParseCurriculum(sys.argv)

#      ___________________
# ___/  class definitions  \_______________________________________________

class game ():

    def IsCurriculumOne(self):
        """Whether Level 1 runs the safe pellet-only curriculum."""
        return self.levelNum == 1 and CURRICULUM_ID == 1

    def defaulthiscorelist(self):
            return [ (100000,"David") , (80000,"Andy") , (60000,"Count Pacula") , (40000,"Cleopacra") , (20000,"Brett Favre") , (10000,"Sergei Pachmaninoff") ]

    def gethiscores(self):
            """If res/hiscore.txt exists, read it. If not, return the default high scores.
               Output is [ (score,name) , (score,name) , .. ]. Always 6 entries."""
            try:
              f=open(os.path.join(SCRIPT_PATH,"res","hiscore.txt"))
              hs=[]
              for line in f:
                while len(line)>0 and (line[0]=="\n" or line[0]=="\r"): line=line[1:]
                while len(line)>0 and (line[-1]=="\n" or line[-1]=="\r"): line=line[:-1]
                score=int(line.split(" ")[0])
                name=line.partition(" ")[2]
                if score>99999999: score=99999999
                if len(name)>22: name=name[:22]
                hs.append((score,name))
              f.close()
              if len(hs)>6: hs=hs[:6]
              while len(hs)<6: hs.append((0,""))
              return hs
            except IOError:
              return self.defaulthiscorelist()

    def writehiscores(self,hs):
            """Given a new list, write it to the default file."""
            fname=os.path.join(SCRIPT_PATH,"res","hiscore.txt")
            f=open(fname,"w")
            for line in hs:
              f.write(str(line[0])+" "+line[1]+"\n")
            f.close()

    def getplayername(self):
            """Ask the player his name, to go on the high-score list."""
            if NO_WX: return USER_NAME
            try:
              import wx
            except:
              print("Pacman Error: No module wx. Can not ask the user his name!")
              print( "     :(       Download wx from http://www.wxpython.org/")
              print( "     :(       To avoid seeing this error again, set NO_WX in file pacman.pyw.")
              return USER_NAME
            app=wx.App(None)
            dlog=wx.TextEntryDialog(None,"You made the high-score list! Name:")
            dlog.ShowModal()
            name=dlog.GetValue()
            dlog.Destroy()
            app.Destroy()
            return name

    def updatehiscores(self,newscore):
            """Add newscore to the high score list, if appropriate."""
            hs=self.gethiscores()
            for line in hs:
              if newscore>=line[0]:
                hs.insert(hs.index(line),(newscore,self.getplayername()))
                hs.pop(-1)
                break
            self.writehiscores(hs)

    def makehiscorelist(self):
            "Read the High-Score file and convert it to a useable Surface."
            # My apologies for all the hard-coded constants.... -Andy
            f=pygame.font.Font(os.path.join(SCRIPT_PATH,"res","VeraMoBd.ttf"),10)
            scoresurf=pygame.Surface((276,86),pygame.SRCALPHA)
            scoresurf.set_alpha(200)
            linesurf=f.render(" "*18+"HIGH SCORES",1,(255,255,0))
            scoresurf.blit(linesurf,(0,0))
            hs=self.gethiscores()
            vpos=0
            for line in hs:
              vpos+=12
              linesurf=f.render(line[1].rjust(22)+str(line[0]).rjust(9),1,(255,255,255))
              scoresurf.blit(linesurf,(0,vpos))
            return scoresurf

    def drawmidgamehiscores(self):
            """Redraw the high-score list image after pacman dies."""
            self.imHiscores=self.makehiscorelist()

    def __init__ (self):
        self.levelNum = 0
        self.score = 0
        self.lives = 3

        # game "mode" variable
        # 1 = normal
        # 2 = hit ghost
        # 3 = game over
        # 4 = wait to start
        # 5 = wait after eating ghost
        # 6 = wait after finishing level
        self.mode = 0
        self.modeTimer = 0
        self.ghostTimer = 0
        self.ghostTimerStartedFrame = -1
        self.ghostValue = 0
        self.fruitTimer = 0
        self.fruitScoreTimer = 0
        self.fruitScorePos = (0, 0)

        self.SetMode( 3 )

        # camera variables
        self.screenPixelPos = (0, 0) # absolute x,y position of the screen from the upper-left corner of the level
        self.screenNearestTilePos = (0, 0) # nearest-tile position of the screen from the UL corner
        self.screenPixelOffset = (0, 0) # offset in pixels of the screen from its nearest-tile position

        self.screenTileSize = (23, 21)
        self.screenSize = (self.screenTileSize[1] * 16, self.screenTileSize[0] * 16)

        # numerical display digits
        self.digit = {}
        for i in range(0, 10, 1):
            self.digit[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text",str(i) + ".gif")).convert()
        self.imLife = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text","life.gif")).convert()
        self.imGameOver = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text","gameover.gif")).convert()
        self.imReady = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text","ready.gif")).convert()
        self.imLogo = pygame.image.load(os.path.join(SCRIPT_PATH,"res","text","logo.gif")).convert()
        self.imHiscores = self.makehiscorelist()

    def StartNewGame (self):
        ResetGameEventLedger()
        self.levelNum = START_LEVEL_NUM
        self.score = 0
        self.lives = 3

        self.SetMode( 4 )
        thisLevel.LoadLevel( thisGame.GetLevelNum() )

    def AddToScore (self, amount, eventType=None, ghostID=None):

        extraLifeSet = [25000, 50000, 100000, 150000]

        for specialScore in extraLifeSet:
            if self.score < specialScore and self.score + amount >= specialScore:
                snd_extralife.play()
                thisGame.lives += 1

        self.score += amount
        if eventType is not None:
            RecordGameEvent(eventType, scoreDelta=amount, ghostID=ghostID)


    def DrawScore (self):
        self.DrawNumber (self.score, 24 + 16, self.screenSize[1] - 24 )

        for i in range(0, self.lives, 1):
            screen.blit (self.imLife, (24 + i * 10 + 16, self.screenSize[1] - 12) )

        if not self.IsCurriculumOne():
            screen.blit (thisFruit.imFruit[ thisFruit.fruitType ], (4 + 16, self.screenSize[1] - 20) )

        if self.mode == 3:
            screen.blit (self.imGameOver, (self.screenSize[0] / 2 - 32, self.screenSize[1] / 2 - 10) )
        elif self.mode == 4:
            screen.blit (self.imReady, (self.screenSize[0] / 2 - 20, self.screenSize[1] / 2 + 12) )

        self.DrawNumber (self.levelNum, 0, self.screenSize[1] - 12 )

    def DrawNumber (self, number, x, y):
        strNumber = str(int(number))
        for i in range(0, len(strNumber), 1):
            iDigit = int(strNumber[i])
            screen.blit (self.digit[ iDigit ], (x + i * 9, y) )

    def FitScreenToLevel (self):
        """Resize the window to fit the entire level and lock the camera."""
        global window, screen
        tileSize = 16
        self.screenTileSize = (thisLevel.lvlHeight, thisLevel.lvlWidth)
        self.screenSize = (thisLevel.lvlWidth * tileSize, thisLevel.lvlHeight * tileSize)
        self.MoveScreen(0, 0)
        window = pygame.display.set_mode(self.screenSize, pygame.DOUBLEBUF | pygame.HWSURFACE)
        screen = pygame.display.get_surface()

    def SmartMoveScreen (self):
        # Keep the full map visible; do not scroll the camera with Pacman.
        self.MoveScreen(0, 0)

    def MoveScreen (self, newX, newY ):
        self.screenPixelPos = (newX, newY)
        self.screenNearestTilePos = (int(newY / 16), int(newX / 16)) # nearest-tile position of the screen from the UL corner
        self.screenPixelOffset = (newX - self.screenNearestTilePos[1]*16, newY - self.screenNearestTilePos[0]*16)

    def GetScreenPos (self):
        return self.screenPixelPos

    def GetLevelNum (self):
        return self.levelNum

    def SetNextLevel (self):
        nextLevel = self.levelNum + 1
        nextLevelPath = os.path.join(SCRIPT_PATH, "res", "levels", str(nextLevel) + ".txt")
        if not os.path.isfile(nextLevelPath):
            # All packaged levels are complete. Keep the final maze visible rather
            # than crashing while trying to load a nonexistent next level.
            self.SetMode( 9 )
            return

        self.levelNum = nextLevel

        self.SetMode( 4 )
        thisLevel.LoadLevel( thisGame.GetLevelNum() )

        player.velX = 0
        player.velY = 0
        player.lastMoveDir = 'S'
        player.anim_pacmanCurrent = player.anim_pacmanS


    def SetMode (self, newMode):
        self.mode = newMode
        self.modeTimer = 0
        # print " ***** GAME MODE IS NOW ***** " + str(newMode)

class node ():

    def __init__ (self):
        self.g = -1 # movement cost to move from previous node to this one (usually +10)
        self.h = -1 # estimated movement cost to move from this node to the ending node (remaining horizontal and vertical steps * 10)
        self.f = -1 # total movement cost of this node (= g + h)
        # parent node - used to trace path back to the starting node at the end
        self.parent = (-1, -1)
        # node type - 0 for empty space, 1 for wall (optionally, 2 for starting node and 3 for end)
        self.type = -1

class path_finder ():

    def __init__ (self):
        # map is a 1-DIMENSIONAL array.
        # use the Unfold( (row, col) ) function to convert a 2D coordinate pair
        # into a 1D index to use with this array.
        self.map = {}
        self.size = (-1, -1) # rows by columns

        self.pathChainRev = ""
        self.pathChain = ""

        # starting and ending nodes
        self.start = (-1, -1)
        self.end = (-1, -1)

        # current node (used by algorithm)
        self.current = (-1, -1)

        # open and closed lists of nodes to consider (used by algorithm)
        self.openList = []
        self.closedList = []

        # used in algorithm (adjacent neighbors path finder is allowed to consider)
        self.neighborSet = [ (0, -1), (0, 1), (-1, 0), (1, 0) ]

    def ResizeMap (self, numRows, numCols):
        self.map = {}
        self.size = (numRows, numCols)

        # initialize path_finder map to a 2D array of empty nodes
        for row in range(0, self.size[0], 1):
            for col in range(0, self.size[1], 1):
                self.Set( row, col, node() )
                self.SetType( row, col, 0 )

    def CleanUpTemp (self):

        # this resets variables needed for a search (but preserves the same map / maze)

        self.pathChainRev = ""
        self.pathChain = ""
        self.current = (-1, -1)
        self.openList = []
        self.closedList = []

    def FindPath (self, startPos, endPos, blockedNodes=None ):

        self.CleanUpTemp()

        # (row, col) tuples
        self.start = startPos
        self.end = endPos
        blockedNodes = set(blockedNodes or ())

        # add start node to open list
        self.AddToOpenList( self.start )
        self.SetG ( self.start, 0 )
        self.SetH ( self.start, 0 )
        self.SetF ( self.start, 0 )

        doContinue = True

        while (doContinue == True):

            thisLowestFNode = self.GetLowestFNode()

            if not thisLowestFNode == self.end and not thisLowestFNode == False:
                self.current = thisLowestFNode
                self.RemoveFromOpenList( self.current )
                self.AddToClosedList( self.current )

                for offset in self.neighborSet:
                    thisNeighbor = (self.current[0] + offset[0], self.current[1] + offset[1])

                    if not thisNeighbor[0] < 0 and not thisNeighbor[1] < 0 and not thisNeighbor[0] > self.size[0] - 1 and not thisNeighbor[1] > self.size[1] - 1 and not self.GetType( thisNeighbor ) == 1 and not thisNeighbor in blockedNodes:
                        cost = self.GetG( self.current ) + 10

                        if self.IsInOpenList( thisNeighbor ) and cost < self.GetG( thisNeighbor ):
                            self.RemoveFromOpenList( thisNeighbor )

                        #if self.IsInClosedList( thisNeighbor ) and cost < self.GetG( thisNeighbor ):
                        #   self.RemoveFromClosedList( thisNeighbor )

                        if not self.IsInOpenList( thisNeighbor ) and not self.IsInClosedList( thisNeighbor ):
                            self.AddToOpenList( thisNeighbor )
                            self.SetG( thisNeighbor, cost )
                            self.CalcH( thisNeighbor )
                            self.CalcF( thisNeighbor )
                            self.SetParent( thisNeighbor, self.current )
            else:
                doContinue = False

        if thisLowestFNode == False:
            return False

        # reconstruct path
        self.current = self.end
        while not self.current == self.start:
            # build a string representation of the path using R, L, D, U
            if self.current[1] > self.GetParent(self.current)[1]:
                self.pathChainRev += 'R'
            elif self.current[1] < self.GetParent(self.current)[1]:
                self.pathChainRev += 'L'
            elif self.current[0] > self.GetParent(self.current)[0]:
                self.pathChainRev += 'D'
            elif self.current[0] < self.GetParent(self.current)[0]:
                self.pathChainRev += 'U'
            self.current = self.GetParent(self.current)
            self.SetType( self.current[0],self.current[1], 4)

        # because pathChainRev was constructed in reverse order, it needs to be reversed!
        for i in range(len(self.pathChainRev) - 1, -1, -1):
            self.pathChain += self.pathChainRev[i]

        # set start and ending positions for future reference
        self.SetType( self.start[0],self.start[1], 2)
        self.SetType( self.end[0],self.start[1], 3)

        return self.pathChain

    def Unfold (self, row,col):
        # this function converts a 2D array coordinate pair (row, col)
        # to a 1D-array index, for the object's 1D map array.
        return (row * self.size[1]) + col

    def Set (self, row,col, newNode):
        # sets the value of a particular map cell (usually refers to a node object)
        self.map[ self.Unfold(row, col) ] = newNode

    def GetType (self,val):
        row,col = val
        return self.map[ self.Unfold(row, col) ].type

    def SetType (self,row,col, newValue):
        self.map[ self.Unfold(row, col) ].type = newValue

    def GetF (self, val):
        row,col = val
        return self.map[ self.Unfold(row, col) ].f

    def GetG (self, val):
        row,col = val
        return self.map[ self.Unfold(row, col) ].g

    def GetH (self, val):
        row,col = val
        return self.map[ self.Unfold(row, col) ].h

    def SetG (self, val, newValue ):
        row,col = val
        self.map[ self.Unfold(row, col) ].g = newValue

    def SetH (self, val, newValue ):
        row,col = val
        self.map[ self.Unfold(row, col) ].h = newValue

    def SetF (self, val, newValue ):
        row,col = val
        self.map[ self.Unfold(row, col) ].f = newValue

    def CalcH (self, val):
        row,col = val
        self.map[ self.Unfold(row, col) ].h = abs(row - self.end[0]) + abs(col - self.end[1])

    def CalcF (self, val):
        row,col = val
        unfoldIndex = self.Unfold(row, col)
        self.map[unfoldIndex].f = self.map[unfoldIndex].g + self.map[unfoldIndex].h

    def AddToOpenList (self, val):
        row,col = val
        self.openList.append( (row, col) )

    def RemoveFromOpenList (self, val ):
        row,col = val
        self.openList.remove( (row, col) )

    def IsInOpenList (self, val ):
        row,col = val
        if self.openList.count( (row, col) ) > 0:
            return True
        else:
            return False

    def GetLowestFNode (self):
        lowestValue = None
        lowestPair = (-1, -1)

        for iOrderedPair in self.openList:
            fValue = self.GetF( iOrderedPair )
            if lowestValue is None or fValue < lowestValue:
                lowestValue = fValue
                lowestPair = iOrderedPair

        if not lowestPair == (-1, -1):
            return lowestPair
        else:
            return False

    def AddToClosedList (self, val ):
        row,col = val
        self.closedList.append( (row, col) )

    def IsInClosedList (self, val ):
        row,col = val
        if self.closedList.count( (row, col) ) > 0:
            return True
        else:
            return False

    def SetParent (self, val, val2 ):
        row,col = val
        parentRow,parentCol = val2
        self.map[ self.Unfold(row, col) ].parent = (parentRow, parentCol)

    def GetParent (self, val ):
        row,col = val
        return self.map[ self.Unfold(row, col) ].parent

    def draw (self):
        for row in range(0, self.size[0], 1):
            for col in range(0, self.size[1], 1):

                thisTile = self.GetType((row, col))
                screen.blit (tileIDImage[ thisTile ], (col * 32, row * 32))

class ghost ():
    def __init__ (self, ghostID):
        self.x = 0
        self.y = 0
        self.velX = 0
        self.velY = 0
        self.speed = 1

        self.nearestRow = 0
        self.nearestCol = 0

        self.id = ghostID

        # ghost "state" variable
        # 1 = normal
        # 2 = vulnerable
        # 3 = spectacles
        # 4 = inactive
        self.state = 1

        self.homeX = 0
        self.homeY = 0

        self.currentPath = ""

        self.anim = {}
        for i in range(1, 7, 1):
            self.anim[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","ghost " + str(i) + ".gif")).convert()

            # change the ghost color in this frame
            for y in range(0, 16, 1):
                for x in range(0, 16, 1):

                    if self.anim[i].get_at( (x, y) ) == (255, 0, 0, 255):
                        # default, red ghost body color
                        self.anim[i].set_at( (x, y), ghostcolor[ self.id ] )

        self.animFrame = 1
        self.animDelay = 0

    def Draw (self):

        if thisGame.mode == 3 or self.state == 4:
            return False


        # ghost eyes --
        for y in range(4, 8, 1):
            for x in range(3, 7, 1):
                self.anim[ self.animFrame ].set_at( (x, y), (255, 255, 255, 255) )
                self.anim[ self.animFrame ].set_at( (x+6, y), (255, 255, 255, 255) )

                if player.x > self.x and player.y > self.y:
                    #player is to lower-right
                    pupilSet = (5, 6)
                elif player.x < self.x and player.y > self.y:
                    #player is to lower-left
                    pupilSet = (3, 6)
                elif player.x > self.x and player.y < self.y:
                    #player is to upper-right
                    pupilSet = (5, 4)
                elif player.x < self.x and player.y < self.y:
                    #player is to upper-left
                    pupilSet = (3, 4)
                else:
                    pupilSet = (4, 6)

        for y in range(pupilSet[1], pupilSet[1] + 2, 1):
            for x in range(pupilSet[0], pupilSet[0] + 2, 1):
                self.anim[ self.animFrame ].set_at( (x, y), (0, 0, 255, 255) )
                self.anim[ self.animFrame ].set_at( (x+6, y), (0, 0, 255, 255) )
        # -- end ghost eyes

        if self.state == 1:
            # draw regular ghost (this one)
            screen.blit (self.anim[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
        elif self.state == 2:
            # draw vulnerable ghost
            if thisGame.ghostTimer > 100:
                # blue
                screen.blit (ghosts[4].anim[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
            else:
                # blue/white flashing
                tempTimerI = int(thisGame.ghostTimer / 10)
                if tempTimerI == 1 or tempTimerI == 3 or tempTimerI == 5 or tempTimerI == 7 or tempTimerI == 9:
                    screen.blit (ghosts[5].anim[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))
                else:
                    screen.blit (ghosts[4].anim[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))

        elif self.state == 3:
            # draw glasses
            screen.blit (tileIDImage[ tileID[ 'glasses' ] ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))

        if thisGame.mode == 6 or thisGame.mode == 7:
            # don't animate ghost if the level is complete
            return False

        self.animDelay += 1

        if self.animDelay == 2:
            self.animFrame += 1

            if self.animFrame == 7:
                # wrap to beginning
                self.animFrame = 1

            self.animDelay = 0

    def Move (self):

        if self.state == 4:
            return

        self.x += self.velX
        self.y += self.velY

        self.nearestRow = int(((self.y + 8) / 16))
        self.nearestCol = int(((self.x + 8) / 16))

        if (self.x % 16) == 0 and (self.y % 16) == 0:
            # if the ghost is lined up with the grid again
            # meaning, it's time to go to the next path item

            if (self.currentPath):
                self.currentPath = self.currentPath[1:]
                self.FollowNextPathWay()

            else:
                self.x = self.nearestCol * 16
                self.y = self.nearestRow * 16

                # chase pac-man
                self.currentPath = self.FindPathTo( (player.nearestRow, player.nearestCol) )
                self.FollowNextPathWay()

    def TileInGhostHouse (self, row, col):
        """Return whether a tile is the door or one of the three pen cells."""
        door = thisLevel.GetGhostBoxPos()
        if not door:
            return False
        doorRow, doorCol = door
        if (row, col) == door:
            return True
        return (
            row == doorRow + 1
            and abs(col - doorCol) <= 1
            and not thisLevel.IsWall(row, col, actor="ghost")
        )

    def IsInGhostHouse (self):
        return self.TileInGhostHouse(self.nearestRow, self.nearestCol)

    def GhostHouseExitTile (self):
        door = thisLevel.GetGhostBoxPos()
        if not door:
            return (self.nearestRow, self.nearestCol)
        return (door[0] - 1, door[1])

    def GhostPenTile (self):
        door = thisLevel.GetGhostBoxPos()
        if not door:
            return (self.nearestRow, self.nearestCol)
        return (door[0] + 1, door[1])

    def FindPathTo (self, target):
        """Find a role-correct path without allowing normal ghosts back inside."""
        blocked = []
        door = thisLevel.GetGhostBoxPos()
        if self.state == 1 and not self.IsInGhostHouse() and door:
            blocked.append(door)
        return path.FindPath(
            (self.nearestRow, self.nearestCol), target, blockedNodes=blocked
        )

    def CanTakePathDirection (self, direction):
        """Normal ghosts may cross the door only while leaving the house."""
        offsets = {"L": (0, -1), "R": (0, 1), "U": (-1, 0), "D": (1, 0)}
        if direction not in offsets:
            return False
        rowOffset, colOffset = offsets[direction]
        target = (
            self.nearestRow + rowOffset,
            self.nearestCol + colOffset,
        )
        door = thisLevel.GetGhostBoxPos()
        if target == door and self.state == 1 and not self.IsInGhostHouse():
            return False
        return not thisLevel.IsWall(target[0], target[1], actor="ghost")

    def FollowNextPathWay (self):

        # print "Ghost " + str(self.id) + " rem: " + self.currentPath

        # False = no path exists. "" = arrived at destination (needs repath below).
        if self.currentPath == False:
            self.velX = 0
            self.velY = 0
            return

        if len(self.currentPath) > 0:
            if not self.CanTakePathDirection(self.currentPath[0]):
                target = (
                    self.GhostPenTile()
                    if self.state == 3
                    else (player.nearestRow, player.nearestCol)
                )
                self.currentPath = self.FindPathTo(target)
                if not self.currentPath:
                    self.velX = 0
                    self.velY = 0
                    return
            if self.currentPath[0] == "L":
                (self.velX, self.velY) = (-self.speed, 0)
            elif self.currentPath[0] == "R":
                (self.velX, self.velY) = (self.speed, 0)
            elif self.currentPath[0] == "U":
                (self.velX, self.velY) = (0, -self.speed)
            elif self.currentPath[0] == "D":
                (self.velX, self.velY) = (0, self.speed)

        else:
            # this ghost has reached his destination!!

            if not self.state == 3:
                # chase pac-man
                self.currentPath = self.FindPathTo( (player.nearestRow, player.nearestCol) )

            else:
                # glasses found way back to ghost box
                self.state = 1
                self.speed = 1
                # Revive in the pen, then leave through the door before chasing.
                self.currentPath = self.FindPathTo(self.GhostHouseExitTile())

            # only take the next step if a real path exists (avoids RecursionError on "")
            if self.currentPath:
                self.FollowNextPathWay()
            else:
                self.velX = 0
                self.velY = 0
class fruit ():
    def __init__ (self):
        # when fruit is not in use, it's in the (-1, -1) position off-screen.
        self.slowTimer = 0
        self.x = -16
        self.y = -16
        self.velX = 0
        self.velY = 0
        self.speed = 1
        self.active = False

        self.bouncei = 0
        self.bounceY = 0

        self.nearestRow = (-1, -1)
        self.nearestCol = (-1, -1)

        self.imFruit = {}
        for i in range(0, 5, 1):
            self.imFruit[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","fruit " + str(i) + ".gif")).convert()

        self.currentPath = ""
        self.fruitType = 1

    def Draw (self):

        if thisGame.mode == 3 or self.active == False:
            return False

        screen.blit (self.imFruit[ self.fruitType ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1] - self.bounceY))


    def Move (self):

        if self.active == False:
            return False

        self.bouncei += 1
        if self.bouncei == 1:
            self.bounceY = 2
        elif self.bouncei == 2:
            self.bounceY = 4
        elif self.bouncei == 3:
            self.bounceY = 5
        elif self.bouncei == 4:
            self.bounceY = 5
        elif self.bouncei == 5:
            self.bounceY = 6
        elif self.bouncei == 6:
            self.bounceY = 6
        elif self.bouncei == 9:
            self.bounceY = 6
        elif self.bouncei == 10:
            self.bounceY = 5
        elif self.bouncei == 11:
            self.bounceY = 5
        elif self.bouncei == 12:
            self.bounceY = 4
        elif self.bouncei == 13:
            self.bounceY = 3
        elif self.bouncei == 14:
            self.bounceY = 2
        elif self.bouncei == 15:
            self.bounceY = 1
        elif self.bouncei == 16:
            self.bounceY = 0
            self.bouncei = 0
            snd_fruitbounce.play()

        self.slowTimer += 1
        if self.slowTimer == 2:
            self.slowTimer = 0

            self.x += self.velX
            self.y += self.velY

            self.nearestRow = int(((self.y + 8) / 16))
            self.nearestCol = int(((self.x + 8) / 16))

            if (self.x % 16) == 0 and (self.y % 16) == 0:
                # if the fruit is lined up with the grid again
                # meaning, it's time to go to the next path item

                if len(self.currentPath) > 0:
                    self.currentPath = self.currentPath[1:]
                    self.FollowNextPathWay()

                else:
                    self.x = self.nearestCol * 16
                    self.y = self.nearestRow * 16

                    self.active = False
                    thisGame.fruitTimer = 0

    def FollowNextPathWay (self):


        # only follow this pathway if there is a possible path found!
        if not self.currentPath == False:

            if len(self.currentPath) > 0:
                if self.currentPath[0] == "L":
                    (self.velX, self.velY) = (-self.speed, 0)
                elif self.currentPath[0] == "R":
                    (self.velX, self.velY) = (self.speed, 0)
                elif self.currentPath[0] == "U":
                    (self.velX, self.velY) = (0, -self.speed)
                elif self.currentPath[0] == "D":
                    (self.velX, self.velY) = (0, self.speed)

class pacman ():

    def __init__ (self):
        self.x = 0
        self.y = 0
        self.velX = 0
        self.velY = 0
        self.speed = 16  # one grid cell per move

        self.nearestRow = 0
        self.nearestCol = 0

        self.homeX = 0
        self.homeY = 0
        self.lastMoveDir = 'S'  # U, D, L, R, or S (stopped)

        self.anim_pacmanL = {}
        self.anim_pacmanR = {}
        self.anim_pacmanU = {}
        self.anim_pacmanD = {}
        self.anim_pacmanS = {}
        self.anim_pacmanCurrent = {}

        for i in range(1, 9, 1):
            self.anim_pacmanL[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman-l " + str(i) + ".gif")).convert()
            self.anim_pacmanR[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman-r " + str(i) + ".gif")).convert()
            self.anim_pacmanU[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman-u " + str(i) + ".gif")).convert()
            self.anim_pacmanD[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman-d " + str(i) + ".gif")).convert()
            self.anim_pacmanS[i] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","sprite","pacman.gif")).convert()

        self.pelletSndNum = 0

    def SnapToGrid (self):
        self.nearestRow = int(((self.y + 8) / 16))
        self.nearestCol = int(((self.x + 8) / 16))
        self.x = self.nearestCol * 16
        self.y = self.nearestRow * 16

    def TryMoveOneCell (self, direction):
        """Move exactly one grid cell in the given direction (U/D/L/R)."""
        self.SnapToGrid()

        delta = { 'U': (0, -16), 'D': (0, 16), 'L': (-16, 0), 'R': (16, 0) }
        if direction not in delta:
            return False

        dx, dy = delta[direction]
        newX = self.x + dx
        newY = self.y + dy
        newRow = int(((newY + 8) / 16))
        newCol = int(((newX + 8) / 16))

        if thisLevel.CheckIfHitWall(newX, newY, newRow, newCol):
            return False

        self.x = newX
        self.y = newY
        self.nearestRow = newRow
        self.nearestCol = newCol
        self.lastMoveDir = direction
        self.velX = 0
        self.velY = 0

        thisLevel.CheckIfHitSomething(self.x, self.y, self.nearestRow, self.nearestCol)
        # A pathway door can teleport the pixel position inside
        # CheckIfHitSomething. Synchronize the cached grid position before
        # collision and fruit events read it into the source event ledger.
        self.SnapToGrid()
        self.CheckGhostCollisions()

        if thisGame.mode != 2 and thisFruit.active == True:
            if thisLevel.CheckIfHit(self.x, self.y, thisFruit.x, thisFruit.y, 8):
                thisFruit.active = False
                thisGame.fruitTimer = 0
                thisGame.fruitScoreTimer = 120
                thisGame.AddToScore(2500, eventType="fruit_eaten")
                snd_eatfruit.play()

        return True

    def CheckGhostCollisions (self):
        """Resolve pacman/ghost overlaps. Cushion matches one tile so mid-cell ghosts still count."""
        if thisGame.mode != 1:
            return

        cushion = 16
        for i in range(0, 4, 1):
            if ghosts[i].state == 4:
                continue
            # Same tile always counts (ghost may be mid-pixel between cells)
            same_tile = (
                ghosts[i].nearestRow == self.nearestRow
                and ghosts[i].nearestCol == self.nearestCol
            )
            if not same_tile and not thisLevel.CheckIfHit(self.x, self.y, ghosts[i].x, ghosts[i].y, cushion):
                continue

            if ghosts[i].state == 1:
                RecordGameEvent("death", scoreDelta=0, ghostID=i)
                thisGame.SetMode(2)
                return
            elif ghosts[i].state == 2:
                if thisGame.ghostValue < 200:
                    thisGame.ghostValue = 200
                ghostScore = thisGame.ghostValue
                thisGame.ghostValue = ghostScore * 2
                snd_eatgh.play()

                ghosts[i].state = 3
                ghosts[i].speed = 4
                ghosts[i].x = ghosts[i].nearestCol * 16
                ghosts[i].y = ghosts[i].nearestRow * 16
                ghosts[i].currentPath = ghosts[i].FindPathTo(
                    ghosts[i].GhostPenTile()
                )
                ghosts[i].FollowNextPathWay()
                thisGame.AddToScore(
                    ghostScore, eventType="ghost_eaten", ghostID=i
                )
                thisGame.SetMode(5)
                return

    def Move (self):

        self.nearestRow = int(((self.y + 8) / 16))
        self.nearestCol = int(((self.x + 8) / 16))

        # deal with power-pellet ghost timer
        if not thisGame.IsCurriculumOne() and thisGame.ghostTimer > 0:
            # CheckIfHitSomething runs before Move in the pellet-contact frame.
            # Do not spend one of the promised 360 logic ticks immediately.
            if thisGame.ghostTimerStartedFrame != GAME_LOGIC_FRAME:
                thisGame.ghostTimer -= 1

            if thisGame.ghostTimer == 0:
                for i in range(0, 4, 1):
                    if ghosts[i].state == 2:
                        ghosts[i].state = 1
                thisGame.ghostValue = 0
                thisGame.ghostTimerStartedFrame = -1

        # Curriculum 1 is pellet-only: fruit never spawns or advances.
        if thisGame.IsCurriculumOne():
            thisFruit.active = False
            thisGame.fruitTimer = 0
            thisGame.fruitScoreTimer = 0
        else:
            thisGame.fruitTimer += 1
        if not thisGame.IsCurriculumOne() and thisGame.fruitTimer == 500:
            pathwayPair = thisLevel.GetPathwayPairPos()

            if not pathwayPair == False:

                pathwayEntrance = pathwayPair[0]
                pathwayExit = pathwayPair[1]

                thisFruit.active = True

                thisFruit.nearestRow = pathwayEntrance[0]
                thisFruit.nearestCol = pathwayEntrance[1]

                thisFruit.x = thisFruit.nearestCol * 16
                thisFruit.y = thisFruit.nearestRow * 16

                thisFruit.currentPath = path.FindPath( (thisFruit.nearestRow, thisFruit.nearestCol), pathwayExit )
                thisFruit.FollowNextPathWay()

        if thisGame.fruitScoreTimer > 0:
            thisGame.fruitScoreTimer -= 1


    def Draw (self):

        if thisGame.mode == 3:
            return False

        # set the current frame array to match the direction pacman is facing
        if self.lastMoveDir == 'R':
            self.anim_pacmanCurrent = self.anim_pacmanR
        elif self.lastMoveDir == 'L':
            self.anim_pacmanCurrent = self.anim_pacmanL
        elif self.lastMoveDir == 'D':
            self.anim_pacmanCurrent = self.anim_pacmanD
        elif self.lastMoveDir == 'U':
            self.anim_pacmanCurrent = self.anim_pacmanU
        else:
            self.anim_pacmanCurrent = self.anim_pacmanS

        screen.blit (self.anim_pacmanCurrent[ self.animFrame ], (self.x - thisGame.screenPixelPos[0], self.y - thisGame.screenPixelPos[1]))

class level ():

    def __init__ (self):
        self.lvlWidth = 0
        self.lvlHeight = 0
        self.edgeLightColor = (255, 255, 0, 255)
        self.edgeShadowColor = (255, 150, 0, 255)
        self.fillColor = (0, 255, 255, 255)
        self.pelletColor = (255, 255, 255, 255)

        self.map = {}

        self.pellets = 0
        self.powerPelletBlinkTimer = 0

    def SetMapTile (self, row, col, newValue):
        self.map[ (row * self.lvlWidth) + col ] = newValue

    def GetMapTile (self, row, col):
        if row >= 0 and row < self.lvlHeight and col >= 0 and col < self.lvlWidth:
            return self.map[ (row * self.lvlWidth) + col ]
        else:
            return 0

    def IsWall (self, row, col, actor="pacman"):
        """Return whether ``actor`` is blocked by this tile.

        Ghost-door tile 1 is a wall for Pacman, but is traversable by normal
        ghosts leaving the pen, vulnerable ghosts, and returning eyes.  The
        normal-ghost no-reentry rule is directional and is enforced by ghost
        path construction.
        """
        if actor not in ("pacman", "ghost", "vulnerable", "eyes"):
            raise ValueError("unknown maze actor: " + str(actor))

        if row > thisLevel.lvlHeight - 1 or row < 0:
            return True

        if col > thisLevel.lvlWidth - 1 or col < 0:
            return True

        # check the offending tile ID
        result = thisLevel.GetMapTile(row, col)

        if result == tileID.get('ghost-door'):
            return actor == "pacman"

        # if the tile was a wall
        if result >= 100 and result <= 199:
            return True
        else:
            return False


    def CheckIfHitWall (self, possiblePlayerX, possiblePlayerY, row, col, actor="pacman"):

        numCollisions = 0

        # check each of the 9 surrounding tiles for a collision
        for iRow in range(row - 1, row + 2, 1):
            for iCol in range(col - 1, col + 2, 1):

                if  (possiblePlayerX - (iCol * 16) < 16) and (possiblePlayerX - (iCol * 16) > -16) and (possiblePlayerY - (iRow * 16) < 16) and (possiblePlayerY - (iRow * 16) > -16):

                    if self.IsWall(iRow, iCol, actor=actor):
                        numCollisions += 1

        if numCollisions > 0:
            return True
        else:
            return False


    def CheckIfHit (self, playerX, playerY, x, y, cushion):

        if (playerX - x < cushion) and (playerX - x > -cushion) and (playerY - y < cushion) and (playerY - y > -cushion):
            return True
        else:
            return False


    def CheckIfHitSomething (self, playerX, playerY, row, col):

        for iRow in range(row - 1, row + 2, 1):
            for iCol in range(col - 1, col + 2, 1):

                if  (playerX - (iCol * 16) < 16) and (playerX - (iCol * 16) > -16) and (playerY - (iRow * 16) < 16) and (playerY - (iRow * 16) > -16):
                    # check the offending tile ID
                    result = thisLevel.GetMapTile(iRow, iCol)

                    if result == tileID[ 'pellet' ]:
                        # got a pellet
                        thisLevel.SetMapTile(iRow, iCol, 0)
                        snd_pellet[player.pelletSndNum].play()
                        player.pelletSndNum = 1 - player.pelletSndNum

                        thisLevel.pellets -= 1

                        thisGame.AddToScore(10, eventType="normal_pellet_eaten")

                        if thisLevel.pellets == 0:
                            # no more pellets left!
                            # WON THE LEVEL
                            RecordGameEvent("level_cleared", scoreDelta=0)
                            thisGame.SetMode( 6 )


                    elif result == tileID[ 'pellet-power' ]:
                        # got a power pellet
                        thisLevel.SetMapTile(iRow, iCol, 0)
                        snd_powerpellet.play()

                        if not thisGame.IsCurriculumOne():
                            thisGame.ghostValue = 200
                            thisGame.ghostTimer = 360
                            thisGame.ghostTimerStartedFrame = GAME_LOGIC_FRAME
                            for i in range(0, 4, 1):
                                if ghosts[i].state == 1:
                                    ghosts[i].state = 2
                        thisGame.AddToScore(
                            100, eventType="power_pellet_eaten"
                        )

                    elif result == tileID[ 'door-h' ]:
                        # ran into a horizontal door
                        for i in range(0, thisLevel.lvlWidth, 1):
                            if not i == iCol:
                                if thisLevel.GetMapTile(iRow, i) == tileID[ 'door-h' ]:
                                    player.x = i * 16

                                    if player.lastMoveDir == 'R':
                                        player.x += 16
                                    elif player.lastMoveDir == 'L':
                                        player.x -= 16

                    elif result == tileID[ 'door-v' ]:
                        # ran into a vertical door
                        for i in range(0, thisLevel.lvlHeight, 1):
                            if not i == iRow:
                                if thisLevel.GetMapTile(i, iCol) == tileID[ 'door-v' ]:
                                    player.y = i * 16

                                    if player.lastMoveDir == 'D':
                                        player.y += 16
                                    elif player.lastMoveDir == 'U':
                                        player.y -= 16

    def GetGhostBoxPos (self):

        for row in range(0, self.lvlHeight, 1):
            for col in range(0, self.lvlWidth, 1):
                if self.GetMapTile(row, col) == tileID[ 'ghost-door' ]:
                    return (row, col)

        return False

    def GetPathwayPairPos (self):

        doorArray = []

        for row in range(0, self.lvlHeight, 1):
            for col in range(0, self.lvlWidth, 1):
                if self.GetMapTile(row, col) == tileID[ 'door-h' ]:
                    # found a horizontal door
                    doorArray.append( (row, col) )
                elif self.GetMapTile(row, col) == tileID[ 'door-v' ]:
                    # found a vertical door
                    doorArray.append( (row, col) )

        if len(doorArray) == 0:
            return False

        chosenDoor = random.randint(0, len(doorArray) - 1)

        if self.GetMapTile( doorArray[chosenDoor][0],doorArray[chosenDoor][1] ) == tileID[ 'door-h' ]:
            # horizontal door was chosen
            # look for the opposite one
            for i in range(0, thisLevel.lvlWidth, 1):
                if not i == doorArray[chosenDoor][1]:
                    if thisLevel.GetMapTile(doorArray[chosenDoor][0], i) == tileID[ 'door-h' ]:
                        return doorArray[chosenDoor], (doorArray[chosenDoor][0], i)
        else:
            # vertical door was chosen
            # look for the opposite one
            for i in range(0, thisLevel.lvlHeight, 1):
                if not i == doorArray[chosenDoor][0]:
                    if thisLevel.GetMapTile(i, doorArray[chosenDoor][1]) == tileID[ 'door-v' ]:
                        return doorArray[chosenDoor], (i, doorArray[chosenDoor][1])

        return False

    def PrintMap (self):

        for row in range(0, self.lvlHeight, 1):
            outputLine = ""
            for col in range(0, self.lvlWidth, 1):

                outputLine += str( self.GetMapTile(row, col) ) + ", "

            # print outputLine

    def DrawMap (self):

        self.powerPelletBlinkTimer += 1
        if self.powerPelletBlinkTimer == 60:
            self.powerPelletBlinkTimer = 0

        for row in range(0, self.lvlHeight, 1):
            for col in range(0, self.lvlWidth, 1):

                useTile = self.GetMapTile(row, col)
                if not useTile == 0 and not useTile == tileID['door-h'] and not useTile == tileID['door-v']:
                    # if this isn't a blank tile

                    if useTile == tileID['pellet-power']:
                        if self.powerPelletBlinkTimer < 30:
                            screen.blit (tileIDImage[ useTile ], (col * 16, row * 16) )

                    elif useTile == tileID['showlogo']:
                        screen.blit (thisGame.imLogo, (col * 16, row * 16) )

                    elif useTile == tileID['hiscores']:
                            screen.blit(thisGame.imHiscores,(col * 16, row * 16))

                    else:
                        screen.blit (tileIDImage[ useTile ], (col * 16, row * 16) )

    def LoadLevel (self, levelNum):

        self.map = {}

        self.pellets = 0

        f = open(os.path.join(SCRIPT_PATH,"res","levels",str(levelNum) + ".txt"), 'r')
        # ANDY -- edit this
        #fileOutput = f.read()
        #str_splitByLine = fileOutput.split('\n')
        lineNum=-1
        rowNum = 0
        useLine = False
        isReadingLevelData = False

        for line in f:

          lineNum += 1

            # print " ------- Level Line " + str(lineNum) + " -------- "
          while len(line)>0 and (line[-1]=="\n" or line[-1]=="\r"): line=line[:-1]
          while len(line)>0 and (line[0]=="\n" or line[0]=="\r"): line=line[1:]
          str_splitBySpace = line.split(' ')


          j = str_splitBySpace[0]

          if (j == "'" or j == ""):
                # comment / whitespace line
                # print " ignoring comment line.. "
                useLine = False
          elif j == "#":
                # special divider / attribute line
                useLine = False

                firstWord = str_splitBySpace[1]

                if firstWord == "lvlwidth":
                    self.lvlWidth = int( str_splitBySpace[2] )
                    # print "Width is " + str( self.lvlWidth )

                elif firstWord == "lvlheight":
                    self.lvlHeight = int( str_splitBySpace[2] )
                    # print "Height is " + str( self.lvlHeight )

                elif firstWord == "edgecolor":
                    # edge color keyword for backwards compatibility (single edge color) mazes
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.edgeLightColor = (red, green, blue, 255)
                    self.edgeShadowColor = (red, green, blue, 255)

                elif firstWord == "edgelightcolor":
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.edgeLightColor = (red, green, blue, 255)

                elif firstWord == "edgeshadowcolor":
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.edgeShadowColor = (red, green, blue, 255)

                elif firstWord == "fillcolor":
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.fillColor = (red, green, blue, 255)

                elif firstWord == "pelletcolor":
                    red = int( str_splitBySpace[2] )
                    green = int( str_splitBySpace[3] )
                    blue = int( str_splitBySpace[4] )
                    self.pelletColor = (red, green, blue, 255)

                elif firstWord == "fruittype":
                    thisFruit.fruitType = int( str_splitBySpace[2] )

                elif firstWord == "startleveldata":
                    isReadingLevelData = True
                        # print "Level data has begun"
                    rowNum = 0

                elif firstWord == "endleveldata":
                    isReadingLevelData = False
                    # print "Level data has ended"

          else:
                useLine = True


            # this is a map data line
          if useLine == True:

                if isReadingLevelData == True:

                    # print str( len(str_splitBySpace) ) + " tiles in this column"

                    for k in range(0, self.lvlWidth, 1):
                        self.SetMapTile(rowNum, k, int(str_splitBySpace[k]) )

                        thisID = int(str_splitBySpace[k])
                        if thisID == 4:
                            # starting position for pac-man

                            player.homeX = k * 16
                            player.homeY = rowNum * 16
                            self.SetMapTile(rowNum, k, 0 )

                        elif thisID >= 10 and thisID <= 13:
                            # one of the ghosts

                            ghosts[thisID - 10].homeX = k * 16
                            ghosts[thisID - 10].homeY = rowNum * 16
                            self.SetMapTile(rowNum, k, 0 )

                        elif thisID == 2:
                            # pellet

                            self.pellets += 1

                    rowNum += 1


        # reload all tiles and set appropriate colors
        GetCrossRef()

        # load map into the pathfinder object
        path.ResizeMap( self.lvlHeight, self.lvlWidth )

        for row in range(0, path.size[0], 1):
            for col in range(0, path.size[1], 1):
                if self.IsWall( row, col, actor="ghost" ):
                    path.SetType( row, col, 1 )
                else:
                    path.SetType( row, col, 0 )

        # do all the level-starting stuff
        self.Restart()
        thisGame.FitScreenToLevel()

    def Restart (self):

        for i in range(0, 4, 1):
            if thisGame.IsCurriculumOne():
                # Preserve the four-ghost schema while removing every source
                # of movement and collision from the safe curriculum.
                ghosts[i].x = -64
                ghosts[i].y = -64
                ghosts[i].velX = 0
                ghosts[i].velY = 0
                ghosts[i].state = 4
                ghosts[i].speed = 1
                ghosts[i].nearestRow = -4
                ghosts[i].nearestCol = -4
                ghosts[i].currentPath = False
                continue

            # move ghosts back to home

            ghosts[i].x = ghosts[i].homeX
            ghosts[i].y = ghosts[i].homeY
            ghosts[i].velX = 0
            ghosts[i].velY = 0
            ghosts[i].state = 1
            ghosts[i].speed = 1
            ghosts[i].nearestRow = int(((ghosts[i].y + 8) / 16))
            ghosts[i].nearestCol = int(((ghosts[i].x + 8) / 16))

            # give each ghost a path to a random spot (containing a pellet)
            (randRow, randCol) = (0, 0)

            while not self.GetMapTile(randRow, randCol) == tileID[ 'pellet' ] or (randRow, randCol) == (0, 0):
                randRow = random.randint(1, self.lvlHeight - 2)
                randCol = random.randint(1, self.lvlWidth - 2)

            # print "Ghost " + str(i) + " headed towards " + str((randRow, randCol))
            ghosts[i].currentPath = ghosts[i].FindPathTo((randRow, randCol))
            ghosts[i].FollowNextPathWay()

        thisFruit.active = False

        if thisGame.IsCurriculumOne():
            thisFruit.x = -64
            thisFruit.y = -64
            thisFruit.velX = 0
            thisFruit.velY = 0
            thisFruit.nearestRow = -4
            thisFruit.nearestCol = -4
            thisFruit.currentPath = False

        thisGame.fruitTimer = 0
        thisGame.ghostTimer = 0
        thisGame.ghostTimerStartedFrame = -1
        thisGame.ghostValue = 0

        player.x = player.homeX
        player.y = player.homeY
        player.velX = 0
        player.velY = 0
        player.lastMoveDir = 'S'
        player.SnapToGrid()

        player.anim_pacmanCurrent = player.anim_pacmanS
        player.animFrame = 3


def CheckIfCloseButton(events):
    for event in events:
        if event.type == pygame.QUIT:
            sys.exit(0)


def CheckInputs(events):
    global agentPaused

    if thisGame.mode == 1:
        # Optional local control channel used by MaaPacman.  Synthetic Win32
        # key presses are unreliable with pygame on some Windows versions,
        # whereas this preserves exactly the same one-cell movement semantics.
        commandFile = os.environ.get('MAAPACMAN_COMMAND_FILE')
        if commandFile:
            try:
                command = open(commandFile, 'r').read().strip()
                if command and command != getattr(CheckInputs, 'lastAgentCommand', None):
                    CheckInputs.lastAgentCommand = command
                    commandID, direction = command.rsplit(',', 1)
                    if direction == 'PAUSE':
                        agentPaused = True
                        moved = None
                        status = 'paused'
                    elif direction == 'RESUME':
                        agentPaused = False
                        moved = None
                        status = 'resumed'
                    elif direction in ('U', 'D', 'L', 'R'):
                        moved = player.TryMoveOneCell(direction)
                        status = 'moved' if moved else 'wall_hit'
                        if moved and thisGame.mode == 1:
                            # Treat one agent action as one grid-cell environment step.
                            # Pac-Man moves 16 pixels atomically, so advance the ghosts
                            # and timers by the matching 16 simulator frames, then remain
                            # paused for the next model decision.
                            for agentFrame in range(0, 16, 1):
                                thisGame.modeTimer += 1
                                # TryMoveOneCell leaves velocity at zero, so this only
                                # advances Pac-Man-owned timers (power pellet and fruit).
                                player.Move()
                                for ghostIndex in range(0, 4, 1):
                                    ghosts[ghostIndex].Move()
                                    player.CheckGhostCollisions()
                                    if thisGame.mode != 1:
                                        break
                                thisFruit.Move()
                                if thisGame.mode != 1:
                                    break
                        agentPaused = True
                    else:
                        moved = None
                        status = 'invalid_command'

                    if direction in ('PAUSE', 'RESUME', 'U', 'D', 'L', 'R'):
                        validDirections = []
                        for label, (dx, dy) in {
                            'U': (0, -16), 'D': (0, 16),
                            'L': (-16, 0), 'R': (16, 0),
                        }.items():
                            x = player.x + dx
                            y = player.y + dy
                            row = int(((y + 8) / 16))
                            col = int(((x + 8) / 16))
                            if not thisLevel.CheckIfHitWall(x, y, row, col):
                                validDirections.append(label)
                        resultFile = os.environ.get('MAAPACMAN_RESULT_FILE')
                        if resultFile:
                            result = {
                                'id': commandID,
                                'status': status,
                                'attempted': direction,
                                'position': [player.nearestRow, player.nearestCol],
                                'valid_directions': validDirections,
                                'ghost_timer': thisGame.ghostTimer,
                                'ghosts': [
                                    {
                                        'position': [ghosts[index].nearestRow, ghosts[index].nearestCol],
                                        'state': ghosts[index].state,
                                    }
                                    for index in range(0, 4, 1)
                                ],
                            }
                            tempResult = resultFile + '.tmp'
                            try:
                                with open(tempResult, 'w') as resultHandle:
                                    json.dump(result, resultHandle)
                                os.replace(tempResult, resultFile)
                            except (IOError, OSError):
                                pass
            except (IOError, OSError):
                pass
        for event in events:
            if event.type == pygame.KEYDOWN:
                if getattr(event, 'repeat', False):
                    continue
                if event.key == pygame.K_RIGHT:
                    player.TryMoveOneCell('R')
                elif event.key == pygame.K_LEFT:
                    player.TryMoveOneCell('L')
                elif event.key == pygame.K_DOWN:
                    player.TryMoveOneCell('D')
                elif event.key == pygame.K_UP:
                    player.TryMoveOneCell('U')
            elif event.type == pygame.JOYHATMOTION and js != None and event.value != (0, 0):
                hatX, hatY = event.value
                if hatX > 0:
                    player.TryMoveOneCell('R')
                elif hatX < 0:
                    player.TryMoveOneCell('L')
                elif hatY > 0:
                    player.TryMoveOneCell('D')
                elif hatY < 0:
                    player.TryMoveOneCell('U')

    for event in events:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            sys.exit(0)

    if thisGame.mode == 3:
        agentStart = False
        commandFile = os.environ.get('MAAPACMAN_COMMAND_FILE')
        if commandFile:
            try:
                command = open(commandFile, 'r').read().strip()
                if command and command != getattr(CheckInputs, 'lastAgentCommand', None):
                    CheckInputs.lastAgentCommand = command
                    agentStart = command.rsplit(',', 1)[-1] == 'START'
            except (IOError, OSError):
                pass
        if agentStart or pygame.key.get_pressed()[ pygame.K_RETURN ] or (js!=None and js.get_button(JS_STARTBUTTON)):
            thisGame.StartNewGame()



#      _____________________________________________
# ___/  function: Get ID-Tilename Cross References  \______________________________________

def GetCrossRef ():

    f = open(os.path.join(SCRIPT_PATH,"res","crossref.txt"), 'r')
    # ANDY -- edit
    #fileOutput = f.read()
    #str_splitByLine = fileOutput.split('\n')

    lineNum = 0
    useLine = False

    for i in f.readlines():
        # print " ========= Line " + str(lineNum) + " ============ "
        while len(i)>0 and (i[-1]=='\n' or i[-1]=='\r'): i=i[:-1]
        while len(i)>0 and (i[0]=='\n' or i[0]=='\r'): i=i[1:]
        str_splitBySpace = i.split(' ')

        j = str_splitBySpace[0]

        if (j == "'" or j == "" or j == "#"):
            # comment / whitespace line
            # print " ignoring comment line.. "
            useLine = False
        else:
            # print str(wordNum) + ". " + j
            useLine = True

        if useLine == True:
            tileIDName[ int(str_splitBySpace[0]) ] = str_splitBySpace[1]
            tileID[ str_splitBySpace[1] ] = int(str_splitBySpace[0])

            thisID = int(str_splitBySpace[0])
            if not thisID in NO_GIF_TILES:
                tileIDImage[ thisID ] = pygame.image.load(os.path.join(SCRIPT_PATH,"res","tiles",str_splitBySpace[1] + ".gif")).convert()
            else:
                    tileIDImage[ thisID ] = pygame.Surface((16,16))

            # change colors in tileIDImage to match maze colors
            for y in range(0, 16, 1):
                for x in range(0, 16, 1):

                    if tileIDImage[ thisID ].get_at( (x, y) ) == (255, 206, 255, 255):
                        # wall edge
                        tileIDImage[ thisID ].set_at( (x, y), thisLevel.edgeLightColor )

                    elif tileIDImage[ thisID ].get_at( (x, y) ) == (132, 0, 132, 255):
                        # wall fill
                        tileIDImage[ thisID ].set_at( (x, y), thisLevel.fillColor )

                    elif tileIDImage[ thisID ].get_at( (x, y) ) == (255, 0, 255, 255):
                        # pellet color
                        tileIDImage[ thisID ].set_at( (x, y), thisLevel.edgeShadowColor )

                    elif tileIDImage[ thisID ].get_at( (x, y) ) == (128, 0, 128, 255):
                        # pellet color
                        tileIDImage[ thisID ].set_at( (x, y), thisLevel.pelletColor )

            # print str_splitBySpace[0] + " is married to " + str_splitBySpace[1]
        lineNum += 1


#      __________________
# ___/  main code block  \_____________________________________________________

# create the pacman
player = pacman()

# create a path_finder object
path = path_finder()

# create ghost objects
ghosts = {}
for i in range(0, 6, 1):
    # remember, ghost[4] is the blue, vulnerable ghost
    ghosts[i] = ghost(i)

# create piece of fruit
thisFruit = fruit()

tileIDName = {} # gives tile name (when the ID# is known)
tileID = {} # gives tile ID (when the name is known)
tileIDImage = {} # gives tile image (when the ID# is known)

# create game and level objects and load first level
thisGame = game()
thisLevel = level()
thisLevel.LoadLevel( thisGame.GetLevelNum() )

window = pygame.display.set_mode( thisGame.screenSize, pygame.DOUBLEBUF | pygame.HWSURFACE )

# initialise the joystick
if pygame.joystick.get_count()>0:
  if JS_DEVNUM<pygame.joystick.get_count(): js=pygame.joystick.Joystick(JS_DEVNUM)
  else: js=pygame.joystick.Joystick(0)
  js.init()
else: js=None

# MaaPacman freezes normal gameplay during a remote model request. Rendering
# and event processing continue so the window remains visible and responsive.
agentPaused = os.environ.get('MAAPACMAN_PAUSE_ON_START') == '1'

while True:

    events = pygame.event.get()
    CheckIfCloseButton( events )

    if thisGame.mode == 1:
        # normal gameplay mode
        if not agentPaused:
            BeginGameLogicFrame()
        CheckInputs( events )

        if not agentPaused:
            thisGame.modeTimer += 1
            player.Move()
            for i in range(0, 4, 1):
                ghosts[i].Move()
                # Resolve the first ghost-to-Pacman contact in this logic frame.
                player.CheckGhostCollisions()
                if thisGame.mode != 1:
                    break
            thisFruit.Move()

    elif thisGame.mode == 2:
        # waiting after getting hit by a ghost
        thisGame.modeTimer += 1

        if thisGame.modeTimer == 90:
            thisLevel.Restart()

            thisGame.lives -= 1
            if thisGame.lives == -1:
                thisGame.updatehiscores(thisGame.score)
                thisGame.SetMode( 3 )
                thisGame.drawmidgamehiscores()
            else:
                thisGame.SetMode( 4 )

    elif thisGame.mode == 3:
        # game over
        CheckInputs( events )

    elif thisGame.mode == 4:
        # waiting to start
        thisGame.modeTimer += 1

        if thisGame.modeTimer == 90:
            thisGame.SetMode( 1 )
            player.SnapToGrid()

    elif thisGame.mode == 5:
        # brief pause after munching a vulnerable ghost
        thisGame.modeTimer += 1

        if thisGame.modeTimer == 30:
            thisGame.SetMode( 1 )

    elif thisGame.mode == 6:
        # pause after eating all the pellets
        thisGame.modeTimer += 1

        if thisGame.modeTimer == 60:
            thisGame.SetMode( 7 )
            oldEdgeLightColor = thisLevel.edgeLightColor
            oldEdgeShadowColor = thisLevel.edgeShadowColor
            oldFillColor = thisLevel.fillColor

    elif thisGame.mode == 7:
        # flashing maze after finishing level
        thisGame.modeTimer += 1

        whiteSet = [10, 30, 50, 70]
        normalSet = [20, 40, 60, 80]

        if not whiteSet.count(thisGame.modeTimer) == 0:
            # member of white set
            thisLevel.edgeLightColor = (255, 255, 255, 255)
            thisLevel.edgeShadowColor = (255, 255, 255, 255)
            thisLevel.fillColor = (0, 0, 0, 255)
            GetCrossRef()
        elif not normalSet.count(thisGame.modeTimer) == 0:
            # member of normal set
            thisLevel.edgeLightColor = oldEdgeLightColor
            thisLevel.edgeShadowColor = oldEdgeShadowColor
            thisLevel.fillColor = oldFillColor
            GetCrossRef()
        elif thisGame.modeTimer == 150:
            thisGame.SetMode ( 8 )

    elif thisGame.mode == 8:
        # blank screen before changing levels
        thisGame.modeTimer += 1
        if thisGame.modeTimer == 10:
            thisGame.SetNextLevel()

    elif thisGame.mode == 9:
        # Terminal success: every packaged level has been completed.
        pass

    thisGame.SmartMoveScreen()

    screen.blit(img_Background, (0, 0))

    if not thisGame.mode == 8:
        thisLevel.DrawMap()

        if thisGame.fruitScoreTimer > 0:
            if thisGame.modeTimer % 2 == 0:
                thisGame.DrawNumber (2500, thisFruit.x - thisGame.screenPixelPos[0] - 16, thisFruit.y - thisGame.screenPixelPos[1] + 4)

        for i in range(0, 4, 1):
            ghosts[i].Draw()
        thisFruit.Draw()
        player.Draw()

        if thisGame.mode == 3:
                screen.blit(thisGame.imHiscores,(32,256))

    if thisGame.mode == 5:
        thisGame.DrawNumber (thisGame.ghostValue / 2, player.x - thisGame.screenPixelPos[0] - 4, player.y - thisGame.screenPixelPos[1] + 6)



    thisGame.DrawScore()

    pygame.display.flip()

    clock.tick (60)
