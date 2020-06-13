import dataclasses
import os
import subprocess
import time

import psutil

import cogs.AstroAPI as AstroAPI
import cogs.ValidateSettings as ValidateSettings
from cogs.AstroLogging import AstroLogging
from cogs.AstroRCON import AstroRCON


class AstroDedicatedServer():
    """
        The Dedicated Server Class.
    """
    @dataclasses.dataclass
    class ServerSettings():
        PublicIP: str = None
        Port: str = None
        ServerName: str = None
        ServerPassword: str = None
        MaximumPlayerCount: str = None
        OwnerName: str = None
        OwnerGuid: str = None
        PlayerActivityTimeout: str = None
        bDisableServerTravel: str = None
        DenyUnlistedPlayers: str = None
        VerbosePlayerProperties: str = None
        AutoSaveGameInterval: str = None
        BackupSaveGamesInterval: str = None
        ActiveSaveFileDescriptiveName: str = None
        ServerGuid: str = None
        ServerAdvertisedName: str = None
        bLoadAutoSave: str = None
        MaxServerFramerate: str = None
        MaxServerIdleFramerate: str = None
        bWaitForPlayersBeforeShutdown: str = None
        ConsolePort: str = None
        ExitSemaphore: str = None
        HeartbeatInterval: str = None

    def __init__(self, astroPath, launcher):
        self.astroPath = astroPath
        self.launcher = launcher
        self.settings = self.ServerSettings()
        self.ipPortCombo = None
        self.process = None
        self.players = {}
        self.onlinePlayers = []
        self.registered = False
        self.LobbyID = None
        self.serverGUID = self.settings.ServerGuid if self.settings.ServerGuid != '' else "REGISTER"

        self.ready = False
        self.refresh_settings()

    def refresh_settings(self):
        self.settings = dataclasses.replace(
            self.settings, **ValidateSettings.get_current_settings(self.astroPath))
        self.ipPortCombo = f'{self.settings.PublicIP}:{self.settings.Port}'

    def start(self):
        cmd = [os.path.join(self.astroPath, "AstroServer.exe"), '-log']
        self.process = subprocess.Popen(cmd)

    def server_loop(self):
        while True:
            if self.process.poll() is not None:
                AstroLogging.logPrint("Server was closed. Restarting..")
                return self.launcher.start_server()

            playerList = AstroRCON.DSListPlayers(self.settings.ConsolePort)
            if playerList is not None:
                self.players = playerList
                curPlayers = [x['playerName']
                              for x in self.players['playerInfo'] if x['inGame']]

                if len(curPlayers) > len(self.onlinePlayers):
                    playerDif = list(set(curPlayers) -
                                     set(self.onlinePlayers))[0]
                    self.onlinePlayers = curPlayers
                    AstroLogging.logPrint(f"Player joining: {playerDif}")
                elif len(curPlayers) < len(self.onlinePlayers):
                    playerDif = list(
                        set(self.onlinePlayers) - set(curPlayers))[0]
                    self.onlinePlayers = curPlayers
                    AstroLogging.logPrint(f"Player left: {playerDif}")
            time.sleep(self.launcher.launcherConfig.ServerStatusFrequency)

    def deregister_all_server(self):
        servers_registered = (AstroAPI.get_server(
            self.ipPortCombo, self.launcher.headers))['data']['Games']
        if (len(servers_registered)) > 0:
            AstroLogging.logPrint(
                f"Attemping to deregister all ({len(servers_registered)}) servers as {self.ipPortCombo}")
            # pprint(servers_registered)
            for reg_srvr in servers_registered:
                AstroLogging.logPrint(f"Deregistering {reg_srvr['LobbyID']}..")
                AstroAPI.deregister_server(
                    reg_srvr['LobbyID'], self.launcher.headers)
            AstroLogging.logPrint("All servers deregistered")
            time.sleep(1)
            return [x['LobbyID'] for x in servers_registered]
        return []

    def kill_server(self, reason):
        AstroLogging.logPrint(f"Kill Server: {reason}")
        try:
            self.deregister_all_server()
        except:
            pass
        # Kill all child processes
        try:
            for child in psutil.Process(self.process.pid).children():
                child.kill()
        except:
            pass
        # Kill current process
        try:
            os.kill(os.getpid(), 9)
        except:
            pass