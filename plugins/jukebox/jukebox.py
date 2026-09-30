from mbiiez.economy_plugin import CvarPlugin


class plugin(CvarPlugin):

    plugin_name = "Jukebox"
    plugin_description = "!jukebox - players pay credits to pick the music; optional random autoplay."
    plugin_requires = ["credits"]
    config_key = "jukebox"
    switches = {"g_economyJukeboxEnable": "1"}
    default_cvars = {
        'g_jukeboxCost': '10',
        'g_jukeboxCooldown': '60',
        'g_jukeboxAutoplay': '0',
        'g_jukeboxAutoplayMax': '300',
    }
    sections = [
        ("Jukebox", [
            ("g_jukeboxCost", "number", "Cost of a Track (credits)",
             'What a player pays to pick a track for everyone.'),
            ("g_jukeboxCooldown", "number", "Seconds Before the Track Can Be Changed",
             'After a pick, how long before anyone can change the music again.'),
            ("g_jukeboxAutoplay", "bool", "Autoplay Random Tracks When Nobody's Pick Is Playing",
             "When nobody has paid for a track, play random ones so there's always music."),
            ("g_jukeboxAutoplayMax", "number", "Longest a Random Track Plays (seconds, 0 = whole track)",
             "Cuts random tracks short after this long, so they don't hog the jukebox."),
        ]),
    ]

    def announce(self):
        return ["^5Pick the music: ^7!jukebox ^5for the favourites, ^7!jukebox <words> ^5to search ~200 tracks, ^7!jukebox <number> ^5plays one."]
