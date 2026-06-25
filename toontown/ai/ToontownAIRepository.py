import time
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.PyDatagram import PyDatagram
from panda3d.core import *
from panda3d.toontown import *

from otp.ai.AIZoneData import AIZoneDataStore
from otp.ai.AIMsgTypes import *
from otp.ai.TimeManagerAI import TimeManagerAI
from otp.distributed.OtpDoGlobals import *
from toontown.ai.HolidayManagerAI import HolidayManagerAI
from toontown.ai.NewsManagerAI import NewsManagerAI
from toontown.ai.WelcomeValleyManagerAI import WelcomeValleyManagerAI
from toontown.building.DistributedTrophyMgrAI import DistributedTrophyMgrAI
from toontown.catalog.CatalogManagerAI import CatalogManagerAI
from toontown.coghq.CogSuitManagerAI import CogSuitManagerAI
from toontown.coghq.CountryClubManagerAI import CountryClubManagerAI
from toontown.coghq.FactoryManagerAI import FactoryManagerAI
from toontown.coghq.LawOfficeManagerAI import LawOfficeManagerAI
from toontown.coghq.MintManagerAI import MintManagerAI
from toontown.coghq.PromotionManagerAI import PromotionManagerAI
from toontown.distributed.ToontownDistrictAI import ToontownDistrictAI
from toontown.distributed.ToontownDistrictStatsAI import ToontownDistrictStatsAI
from toontown.distributed.ToontownInternalRepository import ToontownInternalRepository
from toontown.estate.EstateManagerAI import EstateManagerAI
from toontown.estate.DistributedBankMgrAI import DistributedBankMgrAI
from toontown.hood import ZoneUtil
from toontown.hood.BRHoodDataAI import BRHoodDataAI
from toontown.hood.BossbotHQDataAI import BossbotHQDataAI
from toontown.hood.CSHoodDataAI import CSHoodDataAI
from toontown.hood.CashbotHQDataAI import CashbotHQDataAI
from toontown.hood.DDHoodDataAI import DDHoodDataAI
from toontown.hood.DGHoodDataAI import DGHoodDataAI
from toontown.hood.DLHoodDataAI import DLHoodDataAI
from toontown.hood.GSHoodDataAI import GSHoodDataAI
from toontown.hood.GZHoodDataAI import GZHoodDataAI
from toontown.hood.LawbotHQDataAI import LawbotHQDataAI
from toontown.hood.MMHoodDataAI import MMHoodDataAI
from toontown.hood.OZHoodDataAI import OZHoodDataAI
from toontown.hood.TTHoodDataAI import TTHoodDataAI
from toontown.parties.ToontownTimeManager import ToontownTimeManager
from toontown.pets.PetManagerAI import PetManagerAI
from toontown.quest.QuestManagerAI import QuestManagerAI
from toontown.racing import RaceGlobals
from toontown.fishing.DistributedFishingPondAI import DistributedFishingPondAI
from toontown.racing.DistributedLeaderBoardAI import DistributedLeaderBoardAI
from toontown.racing.DistributedRacePadAI import DistributedRacePadAI
from toontown.racing.DistributedStartingBlockAI import DistributedStartingBlockAI
from toontown.racing.DistributedStartingBlockAI import DistributedViewingBlockAI
from toontown.racing.DistributedViewPadAI import DistributedViewPadAI
from toontown.racing.RaceManagerAI import RaceManagerAI
from toontown.uberdog.DistributedPartyManagerAI import DistributedPartyManagerAI
from toontown.safezone.SafeZoneManagerAI import SafeZoneManagerAI
from toontown.safezone import DistributedPartyGateAI
from toontown.safezone import DistributedFishingSpotAI
from toontown.shtiker.CogPageManagerAI import CogPageManagerAI
from toontown.spellbook.ToontownMagicWordManagerAI import ToontownMagicWordManagerAI
from toontown.suit.SuitInvasionManagerAI import SuitInvasionManagerAI
from toontown.toon import NPCToons
from toontown.toonbase import ToontownGlobals
from toontown.tutorial.TutorialManagerAI import TutorialManagerAI
from toontown.uberdog.DistributedInGameNewsMgrAI import DistributedInGameNewsMgrAI
import os


class ToontownAIRepository(ToontownInternalRepository):
    notify = DirectNotifyGlobal.directNotify.newCategory('ToontownAIRepository')

    def __init__(self, baseChannel, serverId, districtName):
        ToontownInternalRepository.__init__(self, baseChannel, serverId, dcSuffix='AI')
        self.districtName = districtName
        self.doLiveUpdates = config.GetBool('want-live-updates', True)
        self.wantCogdominiums = config.GetBool('want-cogdominiums', True)
        self.useAllMinigames = config.GetBool('want-all-minigames', True)
        self.dataFolder = config.GetString('server-data-folder', '')
        if self.dataFolder:
            self.dataFolder = self.dataFolder + '/'
        self.districtId = None
        self.district = None
        self.districtStats = None
        self.holidayManager = None
        self.zoneDataStore = None
        self.petMgr = None
        self.bankMgr = None
        self.suitInvasionManager = None
        self.zoneAllocator = None
        self.zoneId2owner = {}
        self.questManager = None
        self.promotionMgr = None
        self.cogPageManager = None
        self.raceMgr = None
        self.countryClubMgr = None
        self.factoryMgr = None
        self.mintMgr = None
        self.lawMgr = None
        self.cogSuitMgr = None
        self.timeManager = None
        self.newsManager = None
        self.welcomeValleyManager = None
        self.inGameNewsMgr = None
        self.catalogManager = None
        self.trophyMgr = None
        self.safeZoneManager = None
        self.magicWordManager = None
        self.friendManager = None
        self.toontownFriendsManager = None
        self.estateMgr = None
        self.partyManager = None
        self.zoneTable = {}
        self.dnaStoreMap = {}
        self.dnaDataMap = {}
        self.hoods = []
        self.buildingManagers = {}
        self.suitPlanners = {}
        if simbase.wantBingo:
            self.bingoMgr = None

    def handleConnected(self):
        ToontownInternalRepository.handleConnected(self)

        # Generate our district...
        self.notify.info('Generating district...')
        self.districtId = self.allocateChannel()
        self.district = ToontownDistrictAI(self)
        self.district.setName(self.districtName)
        self.district.generateWithRequiredAndId(self.districtId, self.getGameDoId(), OTP_ZONE_ID_DISTRICTS)

        # Claim ownership of that district...
        self.notify.info('Declaring ownership...')
        self.district.setAI(self.ourChannel)

        # Setup necessary files and things.
        self.setupFiles()
        
        # Create our global objects.
        self.notify.info('Creating global objects...')
        self.createGlobals()
        # Create our local objects.
        self.notify.info('Creating local objects...')
        self.createLocals()



        # Create our zones.
        self.notify.info('Creating zones...')
        self.createZones()

        # Make our district available, and we're done.
        self.district.b_setAvailable(True)
        self.notify.info('Done.')

    def createLocals(self):
        """
        Creates "local" (non-distributed) objects.
        """

        # Create our holiday manager...
        self.holidayManager = HolidayManagerAI(self)

        # Create our zone data store...
        self.zoneDataStore = AIZoneDataStore()

        # Create our pet manager...
        self.petMgr = PetManagerAI(self)

        # Create our suit invasion manager...
        self.suitInvasionManager = SuitInvasionManagerAI(self)

        # Create our zone allocator...
        self.zoneAllocator = UniqueIdAllocator(ToontownGlobals.DynamicZonesBegin, ToontownGlobals.DynamicZonesEnd)

        # Create our quest manager...
        self.questManager = QuestManagerAI(self)

        # Create our promotion manager...
        self.promotionMgr = PromotionManagerAI(self)

        # Create our Cog page manager...
        self.cogPageManager = CogPageManagerAI(self)

        # Create our race manager...
        self.raceMgr = RaceManagerAI(self)

        # Create our country club manager...
        self.countryClubMgr = CountryClubManagerAI(self)

        # Create our factory manager...
        self.factoryMgr = FactoryManagerAI(self)

        # Create our mint manager...
        self.mintMgr = MintManagerAI(self)

        # Create our law office manager...
        self.lawMgr = LawOfficeManagerAI(self)

        # Create our Cog suit manager...
        self.cogSuitMgr = CogSuitManagerAI(self)

        # Create our Toontown time manager...
        self.toontownTimeManager = ToontownTimeManager()
        self.toontownTimeManager.updateLoginTimes(time.time(), time.time(), globalClock.getRealTime())


    def createGlobals(self):
        """
        Creates "global" (distributed) objects.
        """

        # Generate our district stats...
        self.districtStats = ToontownDistrictStatsAI(self)
        self.districtStats.settoontownDistrictId(self.districtId)
        self.districtStats.generateWithRequiredAndId(self.allocateChannel(), self.district.getDoId(),
                                                     OTP_ZONE_ID_DISTRICTS_STATS)

        # Generate our time manager...
        self.timeManager = TimeManagerAI(self)
        self.timeManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our news manager...
        self.newsManager = NewsManagerAI(self)
        self.newsManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        self.dataStoreManager = self.generateGlobalObject(OTP_DO_ID_TOONTOWN_TEMP_STORE_MANAGER, 'DistributedDataStoreManager')

        # Generate our Welcome Valley manager...
        self.welcomeValleyManager = WelcomeValleyManagerAI(self)
        self.welcomeValleyManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our in-game news manager...
        self.inGameNewsMgr = DistributedInGameNewsMgrAI(self)
        self.inGameNewsMgr.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our estate manager...
        self.estateMgr = EstateManagerAI(self)
        self.estateMgr.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our bank manager...
        self.bankMgr = DistributedBankMgrAI(self)
        self.bankMgr.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our catalog manager...
        self.catalogManager = CatalogManagerAI(self)
        self.catalogManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our trophy manager...
        self.trophyMgr = DistributedTrophyMgrAI(self)
        self.trophyMgr.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our safezone manager...
        self.safeZoneManager = SafeZoneManagerAI(self)
        self.safeZoneManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our magic word manager...
        self.magicWordManager = ToontownMagicWordManagerAI(self)
        self.magicWordManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our friend manager...
        self.friendManager = self.generateGlobalObject(OTP_DO_ID_FRIEND_MANAGER, 'FriendManager')

        if __astron__:
            # Generate our Toontown friends manager...
            # TODO: Is this Astron specific?
            self.toontownFriendsManager = self.generateGlobalObject(OTP_DO_ID_TOONTOWN_FRIENDS_MANAGER,
                                                                    'ToontownFriendsManager')

        # Generate our estate manager...
        self.estateMgr = EstateManagerAI(self)
        self.estateMgr.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our Tutorial manager...
        self.tutorialManager = TutorialManagerAI(self)
        self.tutorialManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)

        # Generate our party manager...
        self.partyManager = DistributedPartyManagerAI(self)
        self.partyManager.generateWithRequired(OTP_ZONE_ID_MANAGEMENT)
        

    def generateHood(self, hoodConstructor, zoneId):
        # Bossbot HQ doesn't use DNA, so we skip over that.
        if zoneId != ToontownGlobals.BossbotHQ:
            self.dnaStoreMap[zoneId] = DNAStorage()
            self.dnaDataMap[zoneId] = loadDNAFileAI(self.dnaStoreMap[zoneId], self.genDNAFileName(zoneId))
            if zoneId in ToontownGlobals.HoodHierarchy:
                for streetId in ToontownGlobals.HoodHierarchy[zoneId]:
                    self.dnaStoreMap[streetId] = DNAStorage()
                    self.dnaDataMap[streetId] = loadDNAFileAI(self.dnaStoreMap[streetId], self.genDNAFileName(streetId))

        hood = hoodConstructor(self, zoneId)
        hood.startup()
        self.hoods.append(hood)

    def createZones(self):
        # First, generate our zone2NpcDict...
        NPCToons.generateZone2NpcDict()

        # Donald's Dock
        self.zoneTable[ToontownGlobals.DonaldsDock] = (
            (ToontownGlobals.DonaldsDock, 1, 0), (ToontownGlobals.BarnacleBoulevard, 1, 1),
            (ToontownGlobals.SeaweedStreet, 1, 1), (ToontownGlobals.LighthouseLane, 1, 1)
        )
        self.generateHood(DDHoodDataAI, ToontownGlobals.DonaldsDock)

        # Toontown Central
        self.zoneTable[ToontownGlobals.ToontownCentral] = (
            (ToontownGlobals.ToontownCentral, 1, 0), (ToontownGlobals.SillyStreet, 1, 1),
            (ToontownGlobals.LoopyLane, 1, 1), (ToontownGlobals.PunchlinePlace, 1, 1)
        )
        self.generateHood(TTHoodDataAI, ToontownGlobals.ToontownCentral)

        # The Brrrgh
        self.zoneTable[ToontownGlobals.TheBrrrgh] = (
            (ToontownGlobals.TheBrrrgh, 1, 0), (ToontownGlobals.WalrusWay, 1, 1),
            (ToontownGlobals.SleetStreet, 1, 1), (ToontownGlobals.PolarPlace, 1, 1)
        )
        self.generateHood(BRHoodDataAI, ToontownGlobals.TheBrrrgh)

        # Minnie's Melodyland
        self.zoneTable[ToontownGlobals.MinniesMelodyland] = (
            (ToontownGlobals.MinniesMelodyland, 1, 0), (ToontownGlobals.AltoAvenue, 1, 1),
            (ToontownGlobals.BaritoneBoulevard, 1, 1), (ToontownGlobals.TenorTerrace, 1, 1)
        )
        self.generateHood(MMHoodDataAI, ToontownGlobals.MinniesMelodyland)

        # Daisy Gardens
        self.zoneTable[ToontownGlobals.DaisyGardens] = (
            (ToontownGlobals.DaisyGardens, 1, 0), (ToontownGlobals.ElmStreet, 1, 1),
            (ToontownGlobals.MapleStreet, 1, 1), (ToontownGlobals.OakStreet, 1, 1)
        )
        self.generateHood(DGHoodDataAI, ToontownGlobals.DaisyGardens)

        # Chip 'n Dale's Acorn Acres
        self.zoneTable[ToontownGlobals.OutdoorZone] = (
            (ToontownGlobals.OutdoorZone, 1, 0),
        )
        self.generateHood(OZHoodDataAI, ToontownGlobals.OutdoorZone)

        # Goofy Speedway
        self.zoneTable[ToontownGlobals.GoofySpeedway] = (
            (ToontownGlobals.GoofySpeedway, 1, 0),
        )
        self.generateHood(GSHoodDataAI, ToontownGlobals.GoofySpeedway)

        # Donald's Dreamland
        self.zoneTable[ToontownGlobals.DonaldsDreamland] = (
            (ToontownGlobals.DonaldsDreamland, 1, 0), (ToontownGlobals.LullabyLane, 1, 1),
            (ToontownGlobals.PajamaPlace, 1, 1)
        )
        self.generateHood(DLHoodDataAI, ToontownGlobals.DonaldsDreamland)

        # Bossbot HQ
        self.zoneTable[ToontownGlobals.BossbotHQ] = (
            (ToontownGlobals.BossbotHQ, 0, 0),
        )
        self.generateHood(BossbotHQDataAI, ToontownGlobals.BossbotHQ)

        # Sellbot HQ
        self.zoneTable[ToontownGlobals.SellbotHQ] = (
            (ToontownGlobals.SellbotHQ, 0, 1), (ToontownGlobals.SellbotFactoryExt, 0, 1)
        )
        self.generateHood(CSHoodDataAI, ToontownGlobals.SellbotHQ)

        # Cashbot HQ
        self.zoneTable[ToontownGlobals.CashbotHQ] = (
            (ToontownGlobals.CashbotHQ, 0, 1),
        )
        self.generateHood(CashbotHQDataAI, ToontownGlobals.CashbotHQ)

        # Lawbot HQ
        self.zoneTable[ToontownGlobals.LawbotHQ] = (
            (ToontownGlobals.LawbotHQ, 0, 1),
        )
        self.generateHood(LawbotHQDataAI, ToontownGlobals.LawbotHQ)

        # Chip 'n Dale's MiniGolf
        self.zoneTable[ToontownGlobals.GolfZone] = (
            (ToontownGlobals.GolfZone, 1, 0),
        )
        self.generateHood(GZHoodDataAI, ToontownGlobals.GolfZone)

        # Welcome Valley zones
        self.welcomeValleyManager.createWelcomeValleyZones()

        # Assign the initial suit buildings.
        for suitPlanner in list(self.suitPlanners.values()):
            suitPlanner.assignInitialSuitBuildings()

    def genDNAFileName(self, zoneId):
        canonicalZoneId = ZoneUtil.getCanonicalZoneId(zoneId)
        canonicalHoodId = ZoneUtil.getCanonicalHoodId(canonicalZoneId)
        hood = ToontownGlobals.dnaMap[canonicalHoodId]
        if canonicalHoodId == canonicalZoneId:
            canonicalZoneId = 'sz'
            phase = ToontownGlobals.phaseMap[canonicalHoodId]
        else:
            phase = ToontownGlobals.streetPhaseMap[canonicalHoodId]

        if 'outdoor_zone' in hood or 'golf_zone' in hood:
            phase = '6'

        return 'phase_%s/dna/%s_%s.dna' % (phase, hood, canonicalZoneId)

    def lookupDNAFileName(self, dnaFileName):
        searchPath = DSearchPath()
        searchPath.appendDirectory(Filename('resources/phase_3.5/dna'))
        searchPath.appendDirectory(Filename('resources/phase_4/dna'))
        searchPath.appendDirectory(Filename('resources/phase_5/dna'))
        searchPath.appendDirectory(Filename('resources/phase_5.5/dna'))
        searchPath.appendDirectory(Filename('resources/phase_6/dna'))
        searchPath.appendDirectory(Filename('resources/phase_8/dna'))
        searchPath.appendDirectory(Filename('resources/phase_9/dna'))
        searchPath.appendDirectory(Filename('resources/phase_10/dna'))
        searchPath.appendDirectory(Filename('resources/phase_11/dna'))
        searchPath.appendDirectory(Filename('resources/phase_12/dna'))
        searchPath.appendDirectory(Filename('resources/phase_13/dna'))
        filename = Filename(dnaFileName)
        found = vfs.resolveFilename(filename, searchPath)
        if not found:
            self.notify.warning('lookupDNAFileName - %s not found on:' % dnaFileName)
            print(searchPath)
        else:
            return filename.getFullpath()

    def loadDNAFileAI(self, dnaStore, dnaFileName):
        return loadDNAFileAI(dnaStore, dnaFileName)
    
    #AIGEOM
    def loadDNAFile(self, dnaStore, dnaFile, cs=CSDefault):
        """
        load everything, including geometry
        """
        return loadDNAFile(dnaStore, dnaFile, cs)
    
    def findFishingPonds(self, dnaGroup, zoneId, area, overrideDNAZone = 0):
        """
        Recursively scans the given DNA tree for fishing ponds.  These
        are defined as all the groups whose code includes the string
        "fishing_pond".  For each such group, creates a
        DistributedFishingPondAI.  Returns the list of distributed
        objects and a list of the DNAGroups so we can search them for
        spots and targets.
        """
        fishingPonds = []
        fishingPondGroups = []

        if ((isinstance(dnaGroup, DNAGroup)) and
            # If it is a DNAGroup, and the name starts with fishing_pond, count it
            (str.find(dnaGroup.getName(), 'fishing_pond') >= 0)):
            # Here's a fishing pond!
            fishingPondGroups.append(dnaGroup)
            fp = DistributedFishingPondAI(self, area)
            fp.generateWithRequired(zoneId)
            fishingPonds.append(fp)
        else:
            # Now look in the children
            # Fishing ponds cannot have other ponds in them,
            # so do not search the one we just found:
            # If we come across a visgroup, note the zoneId and then recurse
            if (isinstance(dnaGroup, DNAVisGroup) and not overrideDNAZone):
                # Make sure we get the real zone id, in case we are in welcome valley
                zoneId = ZoneUtil.getTrueZoneId(
                        int(dnaGroup.getName().split(':')[0]), zoneId)
            for i in range(dnaGroup.getNumChildren()):
                childFishingPonds, childFishingPondGroups = self.findFishingPonds(
                        dnaGroup.at(i), zoneId, area, overrideDNAZone)
                fishingPonds += childFishingPonds
                fishingPondGroups += childFishingPondGroups
        return fishingPonds, fishingPondGroups

    def findFishingSpots(self, dnaPondGroup, distPond):
        """
        Scans the given DNAGroup pond for fishing spots.  These
        are defined as all the props whose code includes the string
        "fishing_spot".  Fishing spots should be the only thing under a pond
        node. For each such prop, creates a DistributedFishingSpotAI.
        Returns the list of distributed objects created.
        """
        fishingSpots = []
        # Search the children of the pond
        for i in range(dnaPondGroup.getNumChildren()):
            dnaGroup = dnaPondGroup.at(i)
            if ((isinstance(dnaGroup, DNAProp)) and
                (str.find(dnaGroup.getCode(), 'fishing_spot') >= 0)):
                # Here's a fishing spot!
                pos = dnaGroup.getPos()
                hpr = dnaGroup.getHpr()
                fs = DistributedFishingSpotAI.DistributedFishingSpotAI(
                     self, distPond, pos[0], pos[1], pos[2], hpr[0], hpr[1], hpr[2])
                fs.generateWithRequired(distPond.zoneId)
                fishingSpots.append(fs)
            else:
                self.notify.debug("Found dnaGroup that is not a fishing_spot under a pond group")
        return fishingSpots


    def findPartyHats(self, dnaData, zoneId):
        partyHats = []
        if 'party_gate' in dnaData.getName():
            x, y, z = dnaData.getPos()
            h, p, r = dnaData.getHpr()
            partyHat = DistributedPartyGateAI.DistributedPartyGateAI(self)
            partyHat.generateWithRequired(zoneId)
            partyHats.append(partyHat)
        else:
            if isinstance(dnaData, DNAVisGroup):
                name = dnaData.getName()
                visId = int(name.split(":", 1)[0]) % 1000
                zoneId = ZoneUtil.getHoodId(zoneId) + visId

        for i in range(dnaData.getNumChildren()):
            foundPartyHats = self.findPartyHats(dnaData.at(i), zoneId)
            partyHats.extend(foundPartyHats)

        return partyHats

    def findRacingPads(self, dnaData, zoneId, area, type='racing_pad', overrideDNAZone=False):
        kartPads, kartPadGroups = [], []
        if type in dnaData.getName():
            if type == 'racing_pad':
                nameSplit = dnaData.getName().split('_')
                racePad = DistributedRacePadAI(self)
                racePad.setArea(area)
                racePad.index = int(nameSplit[2])
                racePad.genre = nameSplit[3]
                trackInfo = RaceGlobals.getNextRaceInfo(-1, racePad.genre, racePad.index)
                racePad.setTrackInfo([trackInfo[0], trackInfo[1]])
                racePad.laps = trackInfo[2]
                racePad.generateWithRequired(zoneId)
                kartPads.append(racePad)
                kartPadGroups.append(dnaData)
            elif type == 'viewing_pad':
                viewPad = DistributedViewPadAI(self)
                viewPad.setArea(area)
                viewPad.generateWithRequired(zoneId)
                kartPads.append(viewPad)
                kartPadGroups.append(dnaData)

        for i in range(dnaData.getNumChildren()):
            foundKartPads, foundKartPadGroups = self.findRacingPads(dnaData.at(i), zoneId, area, type, overrideDNAZone)
            kartPads.extend(foundKartPads)
            kartPadGroups.extend(foundKartPadGroups)

        return kartPads, kartPadGroups

    def findStartingBlocks(self, dnaData, kartPad):
        startingBlocks = []
        for i in range(dnaData.getNumChildren()):
            groupName = dnaData.getName()
            block = dnaData.at(i)
            blockName = block.getName()
            if 'starting_block' in blockName:
                cls = DistributedStartingBlockAI if 'racing_pad' in groupName else DistributedViewingBlockAI
                x, y, z = block.getPos()
                h, p, r = block.getHpr()
                padLocationId = int(blockName[-1])
                startingBlock = cls(self, kartPad, x, y, z, h, p, r, padLocationId)
                startingBlock.generateWithRequired(kartPad.zoneId)
                startingBlocks.append(startingBlock)

        return startingBlocks

    def findLeaderBoards(self, dnaData, zoneId):
        leaderBoards = []
        if 'leaderBoard' in dnaData.getName():
            x, y, z = dnaData.getPos()
            h, p, r = dnaData.getHpr()
            leaderBoard = DistributedLeaderBoardAI(self, dnaData.getName(), x, y, z, h, p, r)
            leaderBoard.generateWithRequired(zoneId)
            leaderBoards.append(leaderBoard)

        for i in range(dnaData.getNumChildren()):
            foundLeaderBoards = self.findLeaderBoards(dnaData.at(i), zoneId)
            leaderBoards.extend(foundLeaderBoards)

        return leaderBoards

    def getTrackClsends(self):
        return False

    def getAvatarExitEvent(self, avId):
        return 'distObjDelete-%d' % avId

    def getAvatarDisconnectReason(self, avId):
        return self.timeManager.avId2disconnectcode.get(avId, ToontownGlobals.DisconnectUnknown)

    def getZoneDataStore(self):
        return self.zoneDataStore

    def incrementPopulation(self):
        self.districtStats.b_setAvatarCount(self.districtStats.getAvatarCount() + 1)

    def decrementPopulation(self):
        self.districtStats.b_setAvatarCount(self.districtStats.getAvatarCount() - 1)

    def allocateZone(self, owner=None):
        zoneId = self.zoneAllocator.allocate()
        if owner:
            self.zoneId2owner[zoneId] = owner

        return zoneId

    def deallocateZone(self, zone):
        if self.zoneId2owner.get(zone):
            del self.zoneId2owner[zone]

        self.zoneAllocator.free(zone)

    def getEstate(self, avId, accId, zoneId, callback):
        # OTP used to answer the estate request with a single getEstate query
        # to its db server.  We don't have that on Astron, so we read (or
        # create) the account's estate, its houses and its pets ourselves,
        # then pack the results into the format the old estate code expects and
        # pass them to callback.
        self.notify.debug('getEstate: avId=%s accId=%s zoneId=%s' % (avId, accId, zoneId))
        estateId = 0
        estateVal = {} # {estateFieldName: packedValues}
        avIds = []

        avatars = {} # {avId: {fieldName: [fieldValue]}}

        def __handleGetEstate(dclass, fields):
            if dclass != self.dclassesByName['DistributedEstateAI']:
                self.notify.warning('account %s has a non-estate dclass %s!' % (accId, dclass))
                return

            nonlocal estateVal
            # pack the estate fields the way the estate AI wants to read them
            estateVal = self.packDclassValueDict(dclass, fields)

            # the estate is ready, move on to the houses
            self.getHouses(avId, accId, zoneId, estateId, estateVal, avIds, avatars, callback)

        def __gotAllAvatars():
            if estateId:
                self.dbInterface.queryObject(self.dbId, estateId, __handleGetEstate)
            else:
                # no estate yet, make one and bind it to the account
                def __handleEstateCreated(newEstateId):
                    nonlocal estateId
                    estateId = newEstateId
                    self.dbInterface.updateObject(self.dbId, accId, self.dclassesByName['AstronAccountAI'],
                                                  {'ESTATE_ID': estateId})

                    self.dbInterface.queryObject(self.dbId, estateId, __handleGetEstate)

                self.dbInterface.createObject(self.dbId, self.dclassesByName['DistributedEstateAI'], {},
                                              __handleEstateCreated)

        def __handleGetAvatar(dclass, fields, index):
            if dclass != self.dclassesByName['DistributedToonAI']:
                self.notify.warning('account %s avatar %s has a non-toon dclass %s!' % (accId, avIds[index], dclass))
                return

            fields['avId'] = avIds[index]
            avatars[index] = fields
            if len(avatars) == 6:
                __gotAllAvatars()

        def __handleGetAccount(dclass, fields):
            if dclass != self.dclassesByName['AstronAccountAI']:
                self.notify.warning('account %s has a non-account dclass %s!' % (accId, dclass))
                return

            nonlocal estateId, avIds, avatars
            estateId = fields.get('ESTATE_ID', 0)
            avIds = fields.get('ACCOUNT_AV_SET', [0] * 6)
            # sanitize the av set in case it is the wrong length
            avIds = avIds[:6]
            avIds += [0] * (6 - len(avIds))
            for index, avId in enumerate(avIds):
                if avId == 0:
                    avatars[index] = None
                    continue

                # pull the toon object for each occupied slot
                self.dbInterface.queryObject(self.dbId, avId,
                                             lambda dclass, fields, idx=index: __handleGetAvatar(dclass, fields, idx))

        # start by reading the account
        self.dbInterface.queryObject(self.dbId, accId, __handleGetAccount)

    def getHouses(self, avId, accId, zoneId, estateId, estateVal, avIds, avatars, callback):
        # Second half of getEstate: read (or create) a house for every slot,
        # gather the pet ids, then fire the callback with everything the
        # estate manager needs.
        self.notify.debug('getHouses: accId=%s estateId=%s avIds=%s' % (accId, estateId, avIds))

        houseIds = [0] * len(avIds)
        houseVal = [None] * len(avIds) # [packedHouseValues]

        def __gotAllHouses():
            # a toon brings its pet along to the estate
            petIds = [0] * len(avIds)
            for index in avatars:
                if avatars[index] != None:
                    petId = avatars[index].get('setPetId', [0])[0]
                    if petId != 0:
                        petIds[index] = petId

            # note which toons have already started a garden
            gardensStarted = [False] * len(avIds)
            for index in avatars:
                if avatars[index] != None:
                    gardenStarted = avatars[index].get('setGardenStarted', [0])[0]
                    if gardenStarted:
                        gardensStarted[index] = True

            # everything is loaded, hand it back to the estate manager
            callback(estateId, estateVal, len(houseIds), houseIds, houseVal,
                     petIds, gardensStarted, estateVal)

        def __handleGetHouse(dclass, fields, index):
            nonlocal houseVal
            if dclass != self.dclassesByName['DistributedHouseAI']:
                self.notify.warning('avatar %s has a non-house object with dclass %s!' % (avIds[index], dclass))
                return

            # the house remembers its owner and name from the toon
            fields['setAvatarId'] = [avIds[index]]
            fields['setName'] = avatars[index]['setName']

            houseVal[index] = self.packDclassValueDict(dclass, fields)

            if None not in houseVal:
                __gotAllHouses()

        def __handleHouseCreated(houseId, index):
            nonlocal houseIds, houseVal

            houseIds[index] = houseId
            av = self.doId2do.get(avIds[index])
            if av:
                # toon is online, update it directly
                av.b_setHouseId(houseId)
            else:
                self.dbInterface.updateObject(self.dbId, avIds[index],
                                              self.dclassesByName['DistributedToonAI'],
                                              {'setHouseId': [houseId]})

            __handleGetHouse(self.dclassesByName['DistributedHouseAI'], {}, index)

        for index in avatars:
            if avatars[index] == None:
                # empty slot, no toon to own a house.  give it an id anyway so
                # the slot generates as an empty house
                houseId = self.allocateChannel()
                houseIds[index] = houseId
                houseVal[index] = {}
                if None not in houseVal:
                    __gotAllHouses()
                    return
                else:
                    continue
            houseId = avatars[index].get('setHouseId', [0])[0]
            if houseId == 0:
                # toon has no house yet, make one
                self.dbInterface.createObject(self.dbId, self.dclassesByName['DistributedHouseAI'],
                                              {},
                                              lambda houseId, idx=index: __handleHouseCreated(houseId, idx))
            else:
                houseIds[index] = houseId
                self.dbInterface.queryObject(self.dbId, houseId,
                                             lambda dclass, fields, idx=index: __handleGetHouse(dclass, fields, idx))

    def trueUniqueName(self, idString):
        return self.uniqueName(idString)

    def makeFriends(self, avatarAId, avatarBId, flags, context):
        """
        Requests to make a friendship between avatarA and avatarB with
        the indicated flags (or upgrade an existing friendship with
        the indicated flags).  The context is any arbitrary 32-bit
        integer.  When the friendship is made, or the operation fails,
        the "makeFriendsReply" event is generated, with two
        parameters: an integer result code, and the supplied context.
        """
        if __astron__:
            self.toontownFriendsManager.sendMakeFriends(avatarAId, avatarBId, flags, context)

    def requestSecret(self, requesterId):
        """
        Requests a "secret" from the friends manager.  This is a
        unique string that will be associated with the indicated
        requesterId, for the purposes of authenticating true-life
        friends.

        When the secret is ready, a "requestSecretReply" message will
        be thrown with three parameters: the result code (0 or 1,
        indicating failure or success), the generated secret, and the
        requesterId again.
        """
        if __astron__:
            self.toontownFriendsManager.sendRequestSecret(requesterId)

    def submitSecret(self, avId, secret):
        """
        avId: the avatar id of the friend who requested the secret
        secret: the secret that was requested
        Submits a secret that was previously requested.
        Will submit through the friends manager.
        When the secret is submitted, a "submitSecretReply" message will
        be thrown with two parameters: the result code (0 or 1,
        indicating failure or success), and the requesterId again.
        """
        if __astron__:
            self.toontownFriendsManager.sendSubmitSecret(avId, secret)

    def setupFiles(self):
        if not os.path.exists(self.dataFolder):
            os.mkdir(self.dataFolder)

    # From Anesidora 
    def sendUpdateToDoId(self, dclassName, fieldName, doId, args, channelId=None):
        """
        channelId can be used as a recipient if you want to bypass the normal
        airecv, ownrecv, broadcast, etc.  If you don't include a channelId
        or if channelId == doId, then the normal broadcast options will
        be used.
        
        See Also: def queryObjectField
        """
        dclass=self.dclassesByName.get(dclassName+self.dcSuffix)
        assert dclass is not None
        if channelId is None:
            channelId=doId
        if dclass is not None:
            dg = dclass.aiFormatUpdate(
                    fieldName, doId, channelId, self.ourChannel, args)
            self.send(dg)

    def createDgUpdateToDoId(self, dclassName, fieldName, doId, args,
                         channelId=None):
        """
        channelId can be used as a recipient if you want to bypass the normal
        airecv, ownrecv, broadcast, etc.  If you don't include a channelId
        or if channelId == doId, then the normal broadcast options will
        be used.
        
        This is just like sendUpdateToDoId, but just returns
        the datagram instead of immediately sending it.
        """
        result = None
        dclass=self.dclassesByName.get(dclassName+self.dcSuffix)
        assert dclass is not None
        if channelId is None:
            channelId=doId
        if dclass is not None:
            dg = dclass.aiFormatUpdate(
                    fieldName, doId, channelId, self.ourChannel, args)
            result = dg
        return result

    def sendUpdateToGlobalDoId(self, dclassName, fieldName, doId, args):
        """
        Used for sending messages from an AI directly to an
        uber object.
        """
        dclass = self.dclassesByName.get(dclassName)
        assert dclass, 'dclass %s not found in DC files' % dclassName
        dg = dclass.aiFormatUpdate(
            fieldName, doId, doId, self.ourChannel, args)
        self.send(dg)

    def addPostSocketClose(self, themessage):
        # Time to send a register for channel message to the msgDirector
        datagram = PyDatagram()
#        datagram.addServerControlHeader(CONTROL_ADD_POST_REMOVE)        
        datagram.addInt8(1)
        datagram.addChannel(CONTROL_MESSAGE)
        datagram.addUint16(CONTROL_ADD_POST_REMOVE)

        datagram.addBlob(themessage.getMessage())
        self.send(datagram)

    def addPostSocketCloseUD(self, dclassName, fieldName, doId, args):
        dclass = self.dclassesByName.get(dclassName)
        assert dclass, 'dclass %s not found in DC files' % dclassName
        dg = dclass.aiFormatUpdate(
            fieldName, doId, doId, self.ourChannel, args)
        self.addPostSocketClose(dg)
    # From Anesidora
    def createPondBingoMgrAI(self, estate):
        """
        estate - the estate for which the PBMgrAI should
                be created.
        returns: None

        This method instructs the BingoManagerAI to
        create a new PBMgrAI for a newly generated
        estate.
        """
        # Guard for publish
        if simbase.wantBingo:
            if self.bingoMgr:
                self.notify.info('createPondBingoMgrAI: Creating a DPBMAI for Dynamic Estate')
                self.bingoMgr.createPondBingoMgrAI(estate, 1)

    def handleAvCatch(self, avId, zoneId, catch):
        """
        avId - ID of avatar to update
        zoneId - zoneId of the pond the catch was made in.
                This is used by the BingoManagerAI to
                determine which PBMgrAI needs to update
                the catch.
        catch - a fish tuple of (genus, species)
        returns: None
        
        This method instructs the BingoManagerAI to
        tell the appropriate PBMgrAI to update the
        catch of an avatar at the particular pond. This
        method is called in the FishManagerAI's
        RecordCatch method.
        """
        # Guard for publish
        if simbase.wantBingo:
            if self.bingoMgr:
                self.bingoMgr.setAvCatchForPondMgr(avId, zoneId, catch)
