from direct.directnotify import DirectNotifyGlobal
from panda3d.direct import DCPacker
from otp.distributed.OTPInternalRepository import OTPInternalRepository
from otp.distributed.OtpDoGlobals import *

class ToontownInternalRepository(OTPInternalRepository):
    notify = DirectNotifyGlobal.directNotify.newCategory('ToontownInternalRepository')
    GameGlobalsId = OTP_DO_ID_TOONTOWN

    def __init__(self, baseChannel, serverId=None, dcFileNames=None, dcSuffix='AI', connectMethod=None, threadedNet=None):
        OTPInternalRepository.__init__(self, baseChannel, serverId, dcFileNames, dcSuffix, connectMethod, threadedNet)

    def _isValidPlayerLocation(self, parentId, zoneId):
        if zoneId < 1000 and zoneId != 1:
            return False

        return True
    
    # Anesidora
    def sendUpdateToDoId(self, dclassName, fieldName, doId, args,
                         channelId=None):
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

    def packDclassValueDict(self, dclass, fieldDict):
        """
        Converts a {fieldName: fieldValue} dict into a
        {fieldName: packedFieldValue} dict.

        The database interface hands us unpacked field values, but the OTP
        estate code (initEstateData / initFromServerResponse / directUpdate)
        wants the values packed the way they'd arrive off the wire.
        """
        valueDict = {}
        packer = DCPacker()

        for fieldName in fieldDict:
            field = dclass.getFieldByName(fieldName)

            packer.beginPack(field)
            field.packArgs(packer, fieldDict[fieldName])
            packer.endPack()

            valueDict[fieldName] = packer.getBytes()
            packer.clearData()

        return valueDict
