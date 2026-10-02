from mbiiez.economy_plugin import CvarPlugin


class plugin(CvarPlugin):

    plugin_name = "Casino"
    plugin_description = ("Games for credits: blackjack against the house, pazaak and chance against each other, "
                          "betting on duels, and a raffle - each switched on or off here.")
    plugin_requires = ["credits"]
    config_key = "casino"
    default_cvars = {
        'g_economyPazaakEnable': '1',
        'g_economyChanceEnable': '1',
        'g_economyBlackjackEnable': '1',
        'g_blackjackMaxBet': '50',
        'g_economyBetEnable': '1',
        'g_betWindowSeconds': '30',
        'g_betMax': '100',
        'g_betWinBonus': '20',
        'g_betLoserRefund': '25',
        'g_economyRaffleEnable': '0',
        'g_raffleIntervalMinutes': '60',
        'g_raffleOpenMinutes': '10',
        'g_raffleTicketPrice': '5',
        'g_raffleMinEntrants': '5',
    }
    section_hints = {'Casino: Games': 'Card and chance games for credits - each one can be switched on or off.', 'Casino: Duel Betting': 'Betting on duels between players.', 'Casino: Raffle': 'A regular prize draw.'}
    sections = [
        ("Casino: Games", [
            ("g_economyBlackjackEnable", "bool", "Blackjack (!blackjack, against the house)",
             'A hand of blackjack against the house; blackjack pays 3:2.'),
            ("g_blackjackMaxBet", "number", "Blackjack Maximum Bet (credits)",
             'The most a player can bet on one hand.'),
            ("g_economyPazaakEnable", "bool", "Pazaak (!pazaak, player vs player)",
             'Challenge another player to Pazaak for a pot of credits.'),
            ("g_economyChanceEnable", "bool", "Chance (!chance, red or blue)",
             'Challenge another player: they pick red or blue, the server rolls, the winner takes the pot.'),
        ]),
        ("Casino: Duel Betting", [
            ("g_economyBetEnable", "bool", "Duel Betting (!bet)",
             'Duellists type !bet start in the first 10 seconds; everyone else can back a fighter.'),
            ("g_betWindowSeconds", "number", "Betting Window (seconds, fighters frozen)",
             'How long the fighters are frozen while bets come in.'),
            ("g_betMax", "number", "Maximum Bet on a Fight (credits)",
             'The most one player can bet on a fight.'),
            ("g_betWinBonus", "number", "Win Bonus (credits, up to the stake)",
             'Extra paid to winning backers, up to what they staked.'),
            ("g_betLoserRefund", "number", "Refund to Losers When Nobody Backed the Winner (%)",
             'If nobody backed the winner, losers get this share of their bet back.'),
        ]),
        ("Casino: Raffle", [
            ("g_economyRaffleEnable", "bool", "Raffle (!raffle)",
             'A draw on a timer: players buy tickets, one wins the pool.'),
            ("g_raffleIntervalMinutes", "number", "Minutes Between Draws",
             'Time from one draw to the next.'),
            ("g_raffleOpenMinutes", "number", "Minutes Tickets Are on Sale Before a Draw",
             'Tickets go on sale this long before each draw.'),
            ("g_raffleTicketPrice", "number", "Ticket Price (credits)",
             'Credits a ticket.'),
            ("g_raffleMinEntrants", "number", "Minimum Entrants (fewer = everyone refunded)",
             "With fewer players in the draw than this, it's called off and everyone's refunded."),
        ]),
    ]

    # Each game's own switch (not forced on - they're settings here).
    GAME_SWITCHES = ["g_economyPazaakEnable", "g_economyChanceEnable", "g_economyBlackjackEnable",
                     "g_economyBetEnable", "g_economyRaffleEnable"]

    def setup(self):
        # Kept as they're set, like the switches of the other plugins.
        self.switches = {k: self.cvars.get(k, "0") for k in self.GAME_SWITCHES}

    def announce(self):
        lines = []
        if self.on("g_economyPazaakEnable"):
            lines.append("^5Feeling lucky? ^7!pazaak <player> <credits> ^5challenges someone to Pazaak - winner takes the pot.")
        if self.on("g_economyChanceEnable"):
            lines.append("^5Red or blue? ^7!chance <player> <credits> ^5- they pick a colour, the server rolls, winner takes the pot.")
        if self.on("g_economyBlackjackEnable"):
            lines.append("^5Beat the dealer: ^7!blackjack <credits> ^5deals you a hand (up to "
                         + self.cvars.get("g_blackjackMaxBet", "50") + "). Blackjack pays 3:2.")
        if self.on("g_economyBetEnable"):
            lines.append("^5Want bets on your duel? Bow at someone (^7K^5), they bow back, then type ^7!bet start ^5in the first 10s.")
            lines.append("^5You're both frozen while everyone bets - ^7!bet <fighter> <credits> ^5backs a fighter, winners share the losers' bets.")
        if self.on("g_economyRaffleEnable"):
            lines.append("^5There's a raffle every " + self.cvars.get("g_raffleIntervalMinutes", "60") + " minutes - tickets go on sale before each draw. "
                         "^7!raffle ^5to see the pool.")
        return lines
