# NEON BASTION
### Neon-TDS | A strategy-focused tower defense game

**NEON BASTION** is a neon-styled tower defense game built with Python and Pygame. Build a defense, upgrade your towers, choose perks, and work with friends to stop enemy waves from reaching your shared core.

## Features

- **21 maps**, each with its own visual theme, including icy, desert, and volcanic environments.
- **Tower building and upgrades**, with five levels for each tower and different roles such as damage, support, economy, and summoning.
- **Multiple difficulties** to challenge different strategies and loadouts.
- **Perks and ability perks** that let you customize how you play.
- **Solo play and local Wi-Fi multiplayer** for up to four players.
- **Cooperative defense:** multiplayer teams share a core, while each player manages their own cash, loadout, perks, and towers.
- **2D and 3D views**, plus adjustable camera controls.
- **Player movement:** sprint and jump around the battlefield while managing your defenses.
- **Targeting options** to prioritize enemies by first, last, strongest, or closest.
- **Wave speed controls** and the ability to skip eligible waves.
- **Customizable controls**, with key hints updated to match your settings.
- **Map and event variety**, with themed visuals for towers and enemies.
- **In-game chat** with a word filter.
- **LAN update support** for sharing game updates between PCs on the same network.

## How to Play

1. Choose a map and difficulty.
2. Select towers for your loadout.
3. Place towers where they can defend the route.
4. Earn cash by hitting enemies, then spend it on more towers and upgrades.
5. Use support towers, perks, targeting, and abilities to improve your defense.
6. Keep enemies from overwhelming your core.

In multiplayer, up to four players can cooperate over the same Wi-Fi network. One player hosts a game, and the others join from the **Wi-Fi Play** menu. Everyone needs to use the same game version and be on the same local network.

## Controls

Controls can be changed in **Options → Controls**. The game displays the keys assigned to each action.

| Action | Default control |
| --- | --- |
| Sprint | Hold `Shift` |
| Jump | `Space` |
| Start the next wave in solo play | `G` |
| Place or select a tower | Left-click |
| Cancel placement or selection | Right-click or `Esc` |
| Fullscreen | `F11` |

Other actions, including tower selection, upgrades, selling, abilities, targeting, camera zoom, and chat, are configurable or shown in the in-game controls screen.

## Running from Source

NEON BASTION is written in Python and uses Pygame.

1. Install Python.
2. Install Pygame if it is not already installed:

   ```bash
   py -m pip install pygame
   ```

3. Open a terminal in the folder containing the game source.
4. Run the game file, for example:

   ```bash
   py neon_bastion.py
   ```

The source filename may differ depending on the version you have.

## Project

- **Repository:** [Amogus-stinki/Neon-TDS](https://github.com/Amogus-stinki/Neon-TDS)
- **Game title:** NEON BASTION
- **Technology:** Python + Pygame

This project is actively developed, so features and details may change between versions.

## Notes

- Local Wi-Fi multiplayer requires players to be on the same local network and use compatible versions.
- This repository is the game's source-code project. A packaged executable, if provided separately, may be easier to run without setting up Python.
