##################################################
# The Toontown Offline Magic Word Manager
##################################################
# Author: Benjamin Frisby
# Copyright: Copyright 2020, Toontown Offline
# Credits: Benjamin Frisby, John Cote, Ruby Lord, Frank, Nick, Little Cat, Ooowoo
# License: MIT
# Version: 1.0.0
# Email: belloqzafarian@gmail.com
##################################################

import collections, types

from direct.distributed.ClockDelta import *
from direct.interval.IntervalGlobal import *

from panda3d.otp import NametagGroup, WhisperPopup

from otp.otpbase import OTPLocalizer
from otp.otpbase import OTPGlobals

from . import MagicWordConfig
import time, random, re, json

magicWordIndex = collections.OrderedDict()


class MagicWord:
    notify = DirectNotifyGlobal.directNotify.newCategory('MagicWord')

    # Whether this Magic word should be considered "hidden"
    # If your Toontown source has a page for Magic Words in the Sthickerbook, this will be useful for that
    hidden = False

    # Whether this Magic Word is an administrative command or not
    # Good for config settings where you want to disable cheaty Magic Words, but still want moderation ones
    administrative = False

    # List of names that will also invoke this word - a setHP magic word might have "hp", for example
    # A Magic Word will always be callable with its class name, so you don't have to put that in the aliases
    aliases = None

    # Description of the Magic Word
    # If your Toontown source has a page for Magic Words in the Sthickerbook, this will be useful for that
    desc = MagicWordConfig.MAGIC_WORD_DEFAULT_DESC

    # Advanced description that gives the user a lot more information than normal
    # If your Toontown source has a page for Magic Words in the Sthickerbook, this will be useful for that
    advancedDesc = MagicWordConfig.MAGIC_WORD_DEFAULT_ADV_DESC

    # Default example with for commands with no arguments set
    # If your Toontown source has a page for Magic Words in the Sthickerbook, this will be useful for that
    example = ""

    # The minimum access level required to use this Magic Word
    accessLevel = 'MODERATOR'

    # A restriction on the Magic Word which sets what kind or set of Distributed Objects it can be used on
    # By default, a Magic Word can affect everyone
    affectRange = [MagicWordConfig.AFFECT_SELF, MagicWordConfig.AFFECT_OTHER, MagicWordConfig.AFFECT_BOTH]

    # Where the magic word will be executed -- EXEC_LOC_CLIENT or EXEC_LOC_SERVER
    execLocation = MagicWordConfig.EXEC_LOC_INVALID

    # List of all arguments for this word, with the format [(type, isRequired), (type, isRequired)...]
    # If the parameter is not required, you must provide a default argument: (type, False, default)
    arguments = None

    def __init__(self):
        if self.__class__.__name__ != "MagicWord":
            self.aliases = self.aliases if self.aliases is not None else []
            self.aliases.insert(0, self.__class__.__name__)
            self.aliases = [x.lower() for x in self.aliases]
            self.arguments = self.arguments if self.arguments is not None else []

            if len(self.arguments) > 0:
                for arg in self.arguments:
                    argInfo = ""
                    if not arg[MagicWordConfig.ARGUMENT_REQUIRED]:
                        argInfo += "(default: {0})".format(arg[MagicWordConfig.ARGUMENT_DEFAULT])
                    self.example += "[{0}{1}] ".format(arg[MagicWordConfig.ARGUMENT_NAME], argInfo)

            self.__register()

    def __register(self):
        for wordName in self.aliases:
            if wordName in magicWordIndex:
                self.notify.error('Duplicate Magic Word name or alias detected! Invalid name: {}'. format(wordName))
            magicWordIndex[wordName] = {'class': self,
                                        'classname': self.__class__.__name__,
                                        'hidden': self.hidden,
                                        'administrative': self.administrative,
                                        'aliases': self.aliases,
                                        'desc': self.desc,
                                        'advancedDesc': self.advancedDesc,
                                        'example': self.example,
                                        'execLocation': self.execLocation,
                                        'access': self.accessLevel,
                                        'affectRange': self.affectRange,
                                        'args': self.arguments}

    def loadWord(self, air=None, cr=None, invokerId=None, targets=None, args=None):
        self.air = air
        self.cr = cr
        self.invokerId = invokerId
        self.targets = targets
        self.args = args

    def executeWord(self):
        executedWord = None
        validTargets = len(self.targets)
        for avId in self.targets:
            invoker = None
            toon = None
            if self.air:
                invoker = self.air.doId2do.get(self.invokerId)
                toon = self.air.doId2do.get(avId)
            elif self.cr:
                invoker = self.cr.doId2do.get(self.invokerId)
                toon = self.cr.doId2do.get(avId)
            if hasattr(toon, "getName"):
                name = toon.getName()
            else:
                name = avId

            if not self.validateTarget(toon):
                if len(self.targets) > 1:
                    validTargets -= 1
                    continue
                return "{} is not a valid target!".format(name)

            # TODO: Should we implement locking?
            # if toon.getLocked() and not self.administrative:
            #     if len(self.targets) > 1:
            #         validTargets -= 1
            #         continue
            #     return "{} is currently locked. You can only use administrative commands on them.".format(name)

            if invoker.getAccessLevel() <= toon.getAccessLevel() and toon != invoker:
                if len(self.targets) > 1:
                    validTargets -= 1
                    continue
                targetAccess = OTPGlobals.AccessLevelDebug2Name.get(OTPGlobals.AccessLevelInt2Name.get(toon.getAccessLevel()))
                invokerAccess = OTPGlobals.AccessLevelDebug2Name.get(OTPGlobals.AccessLevelInt2Name.get(invoker.getAccessLevel()))
                return "You don't have a high enough Access Level to target {0}! Their Access Level: {1}. Your Access Level: {2}.".format(name, targetAccess, invokerAccess)

            if self.execLocation == MagicWordConfig.EXEC_LOC_CLIENT:
                self.args = json.loads(self.args)

            executedWord = self.handleWord(invoker, avId, toon, *self.args)
        # If you're only using the Magic Word on one person and there is a response, return that response
        if executedWord and len(self.targets) == 1:
            return executedWord
        # If the amount of targets is higher than one...
        elif validTargets > 0:
            # And it's only 1, and that's yourself, return None
            if validTargets == 1 and self.invokerId in self.targets:
                return None
            # Otherwise, state how many targets you executed it on
            return "Magic Word successfully executed on %s target(s)." % validTargets
        else:
            return "Magic Word unable to execute on any targets."

    def validateTarget(self, target):
        if self.air:
            from toontown.toon.DistributedToonAI import DistributedToonAI
            return isinstance(target, DistributedToonAI)
        elif self.cr:
            from toontown.toon.DistributedToon import DistributedToon
            return isinstance(target, DistributedToon)
        return False

    def handleWord(self, invoker, avId, toon, *args):
        raise NotImplementedError


class SetHP(MagicWord):
    aliases = ["hp", "setlaff", "laff"]
    desc = "Sets the target's current laff."
    advancedDesc = "This Magic Word will change the current amount of laff points the target has to whichever " \
                   "value you specify. You are only allowed to specify a value between -1 and the target's maximum " \
                   "laff points. If you specify a value less than 1, the target will instantly go sad unless they " \
                   "are in Immortal Mode."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("hp", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        hp = args[0]

        if not -1 <= hp <= toon.getMaxHp():
            return "Can't set {0}'s laff to {1}! Specify a value between -1 and {0}'s max laff ({2}).".format(
                toon.getName(), hp, toon.getMaxHp())

        if hp <= 0 and toon.immortalMode:
            return "Can't set {0}'s laff to {1} because they are in Immortal Mode!".format(toon.getName(), hp)

        toon.b_setHp(hp)
        return "{}'s laff has been set to {}.".format(toon.getName(), hp)


class SetMaxHP(MagicWord):
    aliases = ["maxhp", "setmaxlaff", "maxlaff"]
    desc = "Sets the target's max laff."
    advancedDesc = "This Magic Word will change the maximum amount of laff points the target has to whichever value " \
                   "you specify. You are only allowed to specify a value between 15 and 137 laff points."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("maxhp", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        maxhp = args[0]

        if not 15 <= maxhp <= 137:
            return "Can't set {}'s max laff to {}! Specify a value between 15 and 137.".format(toon.getName(), maxhp)

        toon.b_setMaxHp(maxhp)
        toon.toonUp(maxhp)
        return "{}'s max laff has been set to {}.".format(toon.getName(), maxhp)


class ToggleOobe(MagicWord):
    aliases = ["oobe"]
    desc = "Toggles the out of body experience mode, which lets you move the camera freely."
    advancedDesc = "This Magic Word will toggle what is known as 'Out Of Body Experience' Mode, hence the name " \
                   "'Oobe'. When this mode is active, you are able to move the camera around with your mouse- " \
                   "though your camera will still follow your Toon."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.oobe()
        return "Oobe mode has been toggled."


class ToggleRun(MagicWord):
    aliases = ["run"]
    desc = "Toggles run mode, which gives you a faster running speed."
    advancedDesc = "This Magic Word will toggle Run Mode. When this mode is active, the target can run around at a " \
                   "very fast speed."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        from direct.showbase.InputStateGlobal import inputState
        inputState.set('debugRunning', not inputState.isSet('debugRunning'))
        return "Run mode has been toggled."

class MaxToon(MagicWord):
    aliases = ["max", "idkfa"]
    desc = "Maxes your target toon."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toonbase import ToontownGlobals
        from toontown.quest import Quests
        from toontown.suit import SuitDNA
        from toontown.coghq import CogDisguiseGlobals

        # TODO: Handle this better, like giving out all awards, set the quest tier, stuff like that.
        # This is mainly copied from Anesidora just so I can better work on things.
        toon.b_setTrackAccess([1, 1, 1, 1, 1, 1, 1])

        toon.b_setMaxCarry(ToontownGlobals.MaxCarryLimit)
        toon.b_setQuestCarryLimit(ToontownGlobals.MaxQuestCarryLimit)

        toon.experience.maxOutExp()
        toon.d_setExperience(toon.experience.makeNetString())

        toon.inventory.maxOutInv()
        toon.d_setInventory(toon.inventory.makeNetString())

        toon.b_setMaxHp(ToontownGlobals.MaxHpLimit)
        toon.b_setHp(ToontownGlobals.MaxHpLimit)

        toon.b_setMaxMoney(250)
        toon.b_setMoney(toon.maxMoney)
        toon.b_setBankMoney(toon.maxBankMoney)

        toon.b_setQuests([])
        toon.b_setQuestCarryLimit(ToontownGlobals.MaxQuestCarryLimit)
        toon.b_setRewardHistory(Quests.LOOPING_FINAL_TIER, [])

        toon.b_setCogParts([*CogDisguiseGlobals.PartsPerSuitBitmasks])
        toon.b_setCogTypes([SuitDNA.suitsPerDept - 1] * 4)
        toon.b_setCogLevels([ToontownGlobals.MaxCogSuitLevel] * 4)

        return f"Successfully maxed {toon.getName()}!"

class AbortMinigame(MagicWord):
    aliases = ["exitgame", "exitminigame", "quitgame", "quitminigame", "skipgame", "skipminigame"]
    desc = "Aborts an ongoing minigame."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = []

    def handleWord(self, invoker, avId, toon, *args):
        messenger.send("minigameAbort")
        return "Requested minigame abort."

class Minigame(MagicWord):
    aliases = ["mg"]
    desc = "Teleport to or request the next trolley minigame."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("command", str, True), ("minigame", str, False, ''), ("difficulty", float, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        command = args[0]
        minigame = args[1]
        difficulty = args[2]

        from toontown.toonbase import ToontownGlobals
        from toontown.hood import ZoneUtil
        from toontown.minigame import MinigameCreatorAI
        if command in ToontownGlobals.MinigameNames:
            # Shortcut
            minigame = args[0]
            try:
                difficulty = float(args[2])
            except ValueError:
                difficulty = 0
            
            if toon.zoneId in MinigameCreatorAI.MinigameZoneRefs:
                # Already in minigame zone, assume request
                command = "request"
            elif toon.zoneId == ZoneUtil.getSafeZoneId(toon.zoneId):
                # Assume teleport
                command = "teleport"
            else:
                # Request by default
                command = "request"
        
        isTeleport = command in ('teleport', 'tp')
        isRequest = command in ('request', 'next')

        mgId = None
        mgDiff = None if difficulty == 0 else difficulty
        mgKeep = None
        mgSzId = ZoneUtil.getSafeZoneId(toon.zoneId) if isTeleport else None

        if not any ((isTeleport, isRequest)):
            return f"Unknown command or minigame \"{command}\".  Valid commands: \"teleport\", \"request\", or a minigame to automatically teleport or request"

        try:
            mgId = int(minigame)
            if mgId not in ToontownGlobals.MinigameIDs:
                return f"Unknown minigame ID {mgId}."
        except:
            if minigame not in ToontownGlobals.MinigameNames:
                return f"Unknown minigame name \"{minigame}\"."
            mgId = ToontownGlobals.MinigameNames.get(minigame)

        if any((isTeleport, isRequest)):
            if isTeleport and (ZoneUtil.isDynamicZone(toon.zoneId) or not toon.zoneId == mgSzId):
                return "Target needs to be in a playground to teleport to a minigame."
            MinigameCreatorAI.RequestMinigame[avId] = (mgId, mgKeep, mgDiff, mgSzId)
            if isTeleport:
                try:
                    result = MinigameCreatorAI.createMinigame(self.air, [avId], mgSzId)
                except:
                    return f"Unable to create \"{minigame}\" minigame"
        
                minigameZone = result['minigameZone']
                retStr =  f"Teleporting {toon.getName()} to minigame \"{minigame}\""
                if mgDiff:
                    retStr += f" with difficulty {mgDiff}"
                return retStr + "...", avId, ["minigame", "minigame", "", mgSzId, minigameZone, 0]

            # isRequest
            retStr = f"Successfully requested minigame \"{minigame}\""
            if mgDiff:
                retStr += f" with difficulty {mgDiff}"
            return retStr + "."
        
        return f"Unknown command or minigame \"{command}\".  Valid commands: \"teleport\", \"request\", or a minigame to automatically teleport or request"

class Quests(MagicWord):
    aliases = ["quest", "tasks", "task", "toontasks"]
    desc = "Quest manupliation"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("command", str, True), ("index", int, False, -1)]

    def handleWord(self, invoker, avId, toon, *args):
        command = args[0]
        index = args[1]
        """
        Commands:
        - "finish": Finish a task (sets the progress to 1000), finishes all by default
        """
        if command == "finish":
            if index == -1:
                self.air.questManager.completeAllQuestsMagically(toon)
                return "Finished all quests."
            else:
                if self.air.questManager.completeQuestMagically(toon, index):
                    return f"Finished quest {index}."
                return f"Quest {index} not found.  (Hint: Quest indexes start at 0)"
        else:
            return "Valid commands: \"finish\""

class BossBattle(MagicWord):
    aliases = ["boss"]
    desc = "Create a new or manupliate the current boss battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("command", str, True), ("type", str, False, ""), ("start", int, False, 1)]

    def handleWord(self, invoker, avId, toon, *args):
        command = args[0].lower()
        type = args[1].lower()
        start = args[2]

        """
        Commands:
          - create [type] [start: 1]: Creates a boss and teleports to it.
          - start: Starts/Restarts the battle from the beginning.
          - stop: Stops the battle by going to the Frolic state.
          - skip: Skips the boss to the next state (needs getNextState to be implemented).
          - final: Skips the boss to the final round.
          - kill: Skips the boss to the Victory state.
        """

        # create command shortcut:
        if command in ("vp", "cfo", "cj", "ceo"):
            type = command
            command = "create"
            try:
                start = int(args[1])
            except ValueError:
                start = 1
        
        from toontown.suit.DistributedBossCogAI import DistributedBossCogAI
        boss = None
        for do in self.air.doId2do.values():
            if isinstance(do, DistributedBossCogAI):
                if do.isToonKnown(invoker.doId):
                    boss = do
                    break

        if command == "create":
            if boss:
                return "You're already in a boss battle.  Please finish this one."
            if type == "vp":
                from toontown.suit.DistributedSellbotBossAI import DistributedSellbotBossAI
                boss = DistributedSellbotBossAI(self.air)
            elif type == "cfo":
                from toontown.suit.DistributedCashbotBossAI import DistributedCashbotBossAI
                boss = DistributedCashbotBossAI(self.air)
            elif type == "cj":
                from toontown.suit.DistributedLawbotBossAI import DistributedLawbotBossAI
                boss = DistributedLawbotBossAI(self.air)
            elif type == "ceo":
                from toontown.suit.DistributedBossbotBossAI import DistributedBossbotBossAI
                boss = DistributedBossbotBossAI(self.air)
            else:
                return f"Unknown boss type: \"{type}\""
            
            zoneId = self.air.allocateZone()
            boss.generateWithRequired(zoneId)
            if start:
                boss.addToon(avId)
                boss.b_setState('WaitForToons')
            else:
                boss.b_setState('Frolic')

            respText = f"Created {type.upper()} boss battle"
            if not start:
                respText += " in Frolic state"

            return respText + ", teleporting...", ["cogHQLoader", "cogHQBossBattle", "movie" if start else "teleportIn", boss.getHoodId(), boss.zoneId, 0]
        
        # The following commands needs the invoker to be in a boss battle.
        if not boss:
            return "You ain't in a boss battle!  Use the \"create\" command to create a boss battle."

        boss.acceptNewToons()
        if command == "start":
            boss.b_setState('WaitForToons')
            return "Boss battle started!"

        elif command == "stop":
            boss.b_setState("Frolic")
            return "Boss battle stopped!"

        elif command == "skip":
            try:
                nextState = boss.getNextState()
            except NotImplementedError:
                return "\"getNextState\" is not implemented for this boss battle!"
            if nextState:
                boss.b_setState(nextState)
                return f"Skipped to {nextState}!"
            return f"Cannot skip \"{boss.getCurrentOrNextState()}\" state."

        elif command in ("final", "pie", "crane"):
            if boss.dept == 'c':
                boss.b_setState("BattleFour")
            else:
                boss.b_setState("BattleThree")
            return "Skipped to final round!"

        elif command in ("kill", "victory", "finish"):
            boss.b_setState("Victory")
            return "Killed the boss!"

        # The create command is already described when the invoker is not in a battle.  These are the commands
        # they can use INSIDE the battle.
        return respText + f"Unknown command: \"{command}\". Valid commands: \"start\", \"stop\", \"skip\", \"final\", \"kill\"."


# Instantiate all classes defined here to register them.
# A bit hacky, but better than the old system
for item in list(globals().values()):
    if isinstance(item, type) and issubclass(item, MagicWord):
        i = item()
