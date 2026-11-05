# CS2 modded server

Docker server based on `joedwards32/cs2`, with Metamod, CounterStrikeSharp,
MatchZy, [CS2 Retakes](https://github.com/B3none/cs2-retakes),
[Instadefuse](https://github.com/B3none/cs2-instadefuse),
[Retakes Allocator](https://github.com/Micka2302/cs2-retakes-allocator-2.0), and
[Inventory Simulator](https://inventory.cstrike.app/).
Game and mod updates run automatically at startup, including mod prereleases.

## Quick start

Requires Docker Compose, Linux amd64, and at least **60 GB** of free space.
The default configuration is for LAN play.

1. Edit `docker-compose.yml` to configure the server name, passwords, map, and
   admin IDs. Optionally set `CS2_AUTHKEY` to pass an `-authkey` to CS2.
2. Start the server:

   ```sh
   docker compose up -d --build
   docker compose logs -f cs2-server
   ```

## Admins

Set your 17-digit SteamID64 values under `environment` in `docker-compose.yml`:

```yaml
- CS2_ADMIN_STEAMIDS=76561198330843136,76561198000000000
```

You can also supply the values through your terminal's environment variables.

This replaces MatchZy admins and grants `@css/root` in CounterStrikeSharp.
Manual CounterStrikeSharp entries are preserved. Leave the variable empty to
keep existing admins, or use `[]` to remove managed admins.

Apply environment changes by recreating the container:

```sh
docker compose up -d --force-recreate
```

## Switching modes and maps

Use `!pug` or `!retake` to switch modes and load Mirage.
Use `!map` separately to select a different map by name, Workshop ID, or URL.

## Updates

Restart to check for game and mod updates:

```sh
docker compose restart cs2-server
```

To also update the base image:

```sh
docker compose build --pull
docker compose up -d
```

Updates preserve existing configuration and server data. If an update fails,
the server uses the previous installation when all required mod files are present.

## Files

All server data is stored in `./cs2-data`. Edit game settings under
`cs2-data/game/csgo/cfg/` and plugin settings under
`cs2-data/game/csgo/addons/counterstrikesharp/configs/`.
Defaults from this repository's `cfg/` are copied only when missing.
The server always executes `inventory_simulator.cfg` at startup.

To customize the startup hook, edit `pre.sh` here and rebuild; the copy in
`cs2-data` is replaced on startup.

## Pterodactyl

[Pterodactyl setup and Egg import instructions](pterodactyl/README.md).

## Credits

- [kus/cs2-modded-server](https://github.com/kus/cs2-modded-server)
- [joedwards32/CS2](https://github.com/joedwards32/CS2)
- [ianlucas](https://github.com/ianlucas)
