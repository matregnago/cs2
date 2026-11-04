# Pterodactyl

The [Pterodactyl egg](egg-cs2-modded.json) uses the same Linux
amd64 image as Docker Compose. Run these commands from the repository root to build and push
the image to a registry accessible to your Wings node:

```sh
docker build --platform linux/amd64 -t ghcr.io/YOUR_ACCOUNT/cs2:latest .
docker push ghcr.io/YOUR_ACCOUNT/cs2:latest
```

1. In the Panel, go to **Admin → Nests → Import Egg** and import the JSON into
   a nest. Set the egg's Docker image to the exact tag you pushed and keep
   its startup command so the image selects the Wings launcher. For a private
   registry, configure pull credentials on the Wings node.
2. Create a server using that egg with a primary allocation and at least
   **100 GB** of disk space for CS2 and SteamCMD updates. The installer
   downloads App 730 into the server volume.
3. Set `CS2_ADMIN_STEAMIDS` for the chat commands. Set the GSLT and Steam Web
   API key in the Panel if your deployment uses them. Start the server
   from the Panel and use its console for server commands.

The launcher updates CS2 by default and checks for mod updates on every
start. To skip the SteamCMD check, set `CS2_AUTO_UPDATE` to `0`. The
server starts in PUG and reads the same mod defaults as the Compose setup.
