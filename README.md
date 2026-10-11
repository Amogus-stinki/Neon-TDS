# NEON BASTION
### Neon-TDS | A strategy-focused tower defense game

**NEON BASTION** is a neon-styled tower defense game built with Python and Pygame. Build a defense, upgrade your towers, choose perks, and work with friends to stop enemy waves from reaching your shared core.

## Features

- **21 maps** with distinct visual themes.
- **Tower building and upgrades**, with five levels per tower and roles such as damage, support, economy, and summoning.
- **Multiple difficulties** for different challenges and strategies.
- **Perks and ability perks** to customize your playstyle.
- **Solo play and local Wi-Fi multiplayer** for up to four players.
- **Cooperative defense:** players share a core, while each player manages their own cash, loadout, perks, and towers.
- **2D and 3D views**, plus adjustable camera controls.
- **Player movement:** sprint and jump around the battlefield.
- **Targeting options** to prioritize enemies by first, last, strongest, or closest.
- **Wave speed controls** and the ability to skip eligible waves.
- **Customizable controls** shown in the in-game controls screen.
- **Map and event variety**, with themed visuals for towers and enemies.
- **In-game chat** with a word filter.
- **Local-network update support** for sharing game updates between PCs.

## How to Play

1. Choose a map and difficulty.
2. Select towers for your loadout.
3. Place towers where they can defend the route.
4. Earn cash and spend it on more towers and upgrades.
5. Use support towers, perks, targeting, and abilities to strengthen your defense.
6. Stop enemies from overwhelming your core.

### Playing with Friends

NEON BASTION supports up to four players over the same local Wi-Fi network.

1. One player opens **Wi-Fi Play** and selects **Host a Game**.
2. Other players open **Wi-Fi Play** and join the hosted game.
3. If the host does not appear automatically, players can enter the host's displayed network address.
4. The host chooses the map and difficulty and starts the match.

Players need compatible versions of the game and a local network that allows devices to communicate.

## Getting the Game

There are two ways to run NEON BASTION on Windows:

### Windows executable (`.exe`)

If you have a packaged Windows `.exe` build, you can launch the game directly without manually running the Python source file. Keep any files distributed alongside the executable in the same folder unless the release instructions say otherwise.

### Python source (`.py`)

The source version requires Python and Pygame.

1. Install Python.
2. Open Command Prompt in the folder containing the game source.
3. Install Pygame if needed:

   ```bash
   py -m pip install pygame
   ```

4. Run the source file. For example:

   ```bash
   py neon_bastion.py
   ```

The source filename may differ between versions.

## Controls

Controls can be changed in **Options → Controls**. The in-game controls screen displays the keys assigned to each action.

| Action | Control |
| --- | --- |
| Sprint | Hold `Shift` by default |
| Jump | `Space` by default |
| Place or select a tower | Left-click |
| Cancel placement or selection | Right-click or `Esc` |
| Fullscreen | `F11` |

Other actions, including tower selection, upgrades, selling, abilities, targeting, camera zoom, chat, and wave controls, are shown in the game and may be configurable.

## Project

- **Repository:** [Amogus-stinki/Neon-TDS](https://github.com/Amogus-stinki/Neon-TDS)
- **Game title:** NEON BASTION
- **Technology:** Python + Pygame

This project is actively developed, so features and details may change between versions. If a packaged `.exe` is published, check the project's releases or release notes for the matching build and version.

## Notes

- The GitHub repository contains the project source code. A packaged executable may be distributed separately.
- Local Wi-Fi multiplayer requires players to use compatible game versions and the same local network.
