from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject

from . import HouseGlobals

# Every account has six avatar slots, so an estate has six house slots.
NUM_HOUSES = 6


class LoadEstateOperation(DirectObject):
    """
    Loads (and if necessary creates) an estate, its houses and its pets.

    OTP used to do all of this with a single getEstate query that returned the
    estate, all of the houses and all of the pets in one packet. We don't have
    that on Astron, so we start from the account, find or make its estate, then
    its houses and pets, and activate each one into the estate zone as we go.

    When everything is up the manager's callback is run as
    callback(avId, ownerId, estate, houses). estate is None if the load failed.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('LoadEstateOperation')

    def __init__(self, mgr, callback):
        self.mgr = mgr
        self.air = mgr.air
        self.callback = callback

        self.avId = 0
        self.ownerId = 0
        self.zoneId = 0

        self.accountId = 0
        self.account = None
        self.avIds = [0] * NUM_HOUSES   # the account's ACCOUNT_AV_SET

        self.estateId = 0
        self.estate = None

        self.houses = [None] * NUM_HOUSES
        self.pendingHouses = set()
        self.petIds = []

        self.done = False

    def start(self, avId, ownerId, zoneId):
        self.avId = avId
        self.ownerId = ownerId
        self.zoneId = zoneId

        # We only ever build an estate for the owner going to his own estate,
        # so the message sender's account is the one that owns it.
        self.accountId = self.air.getAccountIdFromSender()
        if not self.accountId:
            self.__fail('no account on the message sender')
            return

        self.air.dbInterface.queryObject(self.air.dbId, self.accountId,
                                         self.__handleAccountRetrieved)

    def __handleAccountRetrieved(self, dclass, fields):
        if fields is None:
            self.__fail("account %s wasn't found in the database" % self.accountId)
            return

        self.account = fields

        # Grab the avatar set and pad it out to a full six slots.
        avIds = list(fields.get('ACCOUNT_AV_SET', []))[:NUM_HOUSES]
        avIds += [0] * (NUM_HOUSES - len(avIds))
        self.avIds = avIds

        self.estateId = fields.get('ESTATE_ID', 0)
        if self.estateId:
            self.__activateEstate()
        else:
            # First time this account has visited an estate; make one.
            self.__createEstate()

    def __createEstate(self):
        # Fill in all of the estate's db fields. The ram fields (clouds, dawn
        # time, treasures and so on) get their dc defaults when we activate.
        fields = {
            'setEstateType': (0,),
            'setLastEpochTimeStamp': (0,),
            'setRentalTimeStamp': (0,),
            'setRentalType': (0,),
            'setDecorData': ([],),
        }
        for i in range(NUM_HOUSES):
            fields['setSlot%dToonId' % i] = (self.avIds[i],)
            fields['setSlot%dItems' % i] = ([],)

        self.air.dbInterface.createObject(self.air.dbId,
                                         self.air.dclassesByName['DistributedEstateAI'],
                                         fields, self.__handleEstateCreated)

    def __handleEstateCreated(self, estateId):
        if not estateId:
            self.__fail('the database could not create an estate')
            return

        self.estateId = estateId

        # Remember the estate on the account so we find it next time.
        self.air.dbInterface.updateObject(self.air.dbId, self.accountId,
                                         self.air.dclassesByName['AstronAccountAI'],
                                         {'ESTATE_ID': estateId})

        self.__activateEstate()

    def __activateEstate(self):
        # Activating the row hands it to the DBSS, which generates a live
        # DistributedEstateAI for us in the estate zone and fires its
        # generate event.
        self.acceptOnce('generate-%d' % self.estateId, self.__handleEstateGenerated)
        self.air.sendActivate(self.estateId, self.air.districtId, self.zoneId)

    def __handleEstateGenerated(self, estate):
        self.estate = estate
        # The estate hangs its butterflies and pets off a single avId; use
        # the owner's.
        estate.avId = self.ownerId
        self.__loadHouses()

    def __loadHouses(self):
        self.pendingHouses = set(range(NUM_HOUSES))
        for i in range(NUM_HOUSES):
            avId = self.avIds[i]
            if not avId:
                # Empty slot. We still want a house standing there, but there's
                # no toon to own it, so make a throwaway one that isn't saved.
                self.__makeEmptyHouse(i)
                continue

            # One query gives us the toon's house, pet and name all at once.
            def gotToon(dclass, fields, i=i, avId=avId):
                self.__handleToonRetrieved(i, avId, dclass, fields)

            self.air.dbInterface.queryObject(self.air.dbId, avId, gotToon)

    def __handleToonRetrieved(self, index, avId, dclass, fields):
        if fields is None:
            self.notify.warning('toon %s (slot %s) is missing, making an empty house' %
                                (avId, index))
            self.__makeEmptyHouse(index)
            return

        houseId = fields.get('setHouseId', (0,))[0]
        petId = fields.get('setPetId', (0,))[0]
        name = fields.get('setName', ('',))[0]

        if petId:
            self.petIds.append(petId)

        if houseId:
            self.__activateHouse(index, houseId, avId)
        else:
            # This toon has never had a house, so build one and remember it.
            self.__createHouse(index, avId, name, linkToon=True)

    def __createHouse(self, index, ownerId, name, linkToon=False):
        # An empty interior (no wallpaper or windows) is the signal
        # setupEnvirons uses to lay down the starter furniture.
        fields = {
            'setHouseType': (HouseGlobals.HOUSE_DEFAULT,),
            'setGardenPos': (index,),
            'setAvatarId': (ownerId,),
            'setName': (name,),
            'setColor': (index,),
            'setAtticItems': (b'',),
            'setInteriorItems': (b'',),
            'setAtticWallpaper': (b'',),
            'setInteriorWallpaper': (b'',),
            'setAtticWindows': (b'',),
            'setInteriorWindows': (b'',),
            'setDeletedItems': (b'',),
        }

        def created(houseId, index=index, ownerId=ownerId, linkToon=linkToon):
            if not houseId:
                self.notify.warning('the database could not create a house for slot %s' % index)
                self.__houseFinished(index)
                return

            if linkToon and ownerId:
                self.air.dbInterface.updateObject(self.air.dbId, ownerId,
                                                 self.air.dclassesByName['DistributedToonAI'],
                                                 {'setHouseId': (houseId,)})
                av = self.air.doId2do.get(ownerId)
                if av:
                    av.b_setHouseId(houseId)

            self.__activateHouse(index, houseId, ownerId)

        self.air.dbInterface.createObject(self.air.dbId,
                                         self.air.dclassesByName['DistributedHouseAI'],
                                         fields, created)

    def __makeEmptyHouse(self, index):
        # A house for an empty slot. We generate it straight onto the state
        # server with no database object behind it, so it just goes away when
        # the estate unloads.
        from . import DistributedHouseAI

        house = DistributedHouseAI.DistributedHouseAI(self.air)
        house.setHousePos(index)
        house.setColor(index)
        house.setGardenPos(index)
        house.setHouseType(HouseGlobals.HOUSE_DEFAULT)
        house.setAvatarId(0)
        house.setName('')
        house.generateWithRequired(self.zoneId)
        self.__handleHouseGenerated(index, house)

    def __activateHouse(self, index, houseId, ownerId):
        # setHousePos isn't a db field, so the row doesn't know where it sits.
        # Pass the slot index along with the activation.
        def generated(house, index=index):
            self.__handleHouseGenerated(index, house)

        self.acceptOnce('generate-%d' % houseId, generated)
        self.air.sendActivate(houseId, self.air.districtId, self.zoneId,
                             self.air.dclassesByName['DistributedHouseAI'],
                             {'setHousePos': (index,)})

    def __handleHouseGenerated(self, index, house):
        house.estate = self.estate
        self.houses[index] = house
        self.estate.houses[index] = house
        self.estate.houseList.append(house)

        if simbase.config.GetBool('want-gardening', True) and hasattr(house, 'createGardenManager'):
            house.createGardenManager()

        self.__houseFinished(index)

    def __houseFinished(self, index):
        self.pendingHouses.discard(index)
        if not self.pendingHouses:
            self.__finish()

    def __finish(self):
        if self.done:
            return
        self.done = True

        # Tell the estate about the pets (it uses them for pet collisions) and
        # bring the pet objects into the zone.
        self.estate.setPetIds(self.petIds)
        for petId in self.petIds:
            self.air.sendActivate(petId, self.air.districtId, self.zoneId)

        # Now that the houses exist, start the rentals and the gardens.
        self.estate.postHouseInit()
        avIdList = [house.ownerId if house else 0 for house in self.houses]
        self.estate.gardenInit(avIdList)

        self.ignoreAll()
        self.callback(self.avId, self.ownerId, self.estate, self.houses)

    def __fail(self, message):
        self.notify.warning(message)
        self.ignoreAll()
        if not self.done:
            self.done = True
            self.callback(self.avId, self.ownerId, None, self.houses)
