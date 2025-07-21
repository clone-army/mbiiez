import time
import random
import re
import threading
import math

class plugin:
    """
    RTV & RTM Plugin for MBIIEZ - Port of original RTVRTM script
    
    Maintains compatibility with original RTVRTM behavior and commands
    """
    plugin_name = "RTVRTM"
    plugin_author = "MBIIEZ Team"
    plugin_url = ""

    COLOR_RED = '^1'
    COLOR_WHITE = '^7'
    COLOR_GREEN = '^2'

    def __init__(self, instance):
        self.instance = instance
        cfg = instance.config.get('plugins', {}).get('rtvrtm', {})
        
        # Core settings - match original defaults
        self.enable_rtv = cfg.get('enable_rtv', True)
        self.enable_rtm = cfg.get('enable_rtm', True)
        self.rtv_vote_time = cfg.get('rtv_vote_time', 30)
        self.rtv_cool_down = cfg.get('rtv_cool_down', 300)  # 5 minutes like original
        self.rtv_percentage = cfg.get('rtv_percentage', 50)
        self.rtv_win_percentage = cfg.get('rtv_win_percentage', 50)
        self.rtm_vote_time = cfg.get('rtm_vote_time', 30)
        self.rtm_cool_down = cfg.get('rtm_cool_down', 300)  # 5 minutes like original
        self.rtm_percentage = cfg.get('rtm_percentage', 50)
        self.rtm_win_percentage = cfg.get('rtm_win_percentage', 50)
        
        # Map configuration
        self.primary_maps = cfg.get('primary_maps', [])
        self.secondary_maps = cfg.get('secondary_maps', [])
        self.rtm_modes = cfg.get('rtm_modes', ['Open', 'Semi-Authentic', 'Full-Authentic', 'Duel', 'Legends'])
        
        # State variables
        self.last_cmd_time = {}
        self.nominations = {}
        self.rtv_votes = set()
        self.rtv_active = False
        self.rtv_timer = None
        self.next_map = None
        self.map_vote_opts = []
        self.map_votes = {}
        self.rtm_votes = set()
        self.rtm_active = False
        self.rtm_timer = None
        self.next_mode = None
        self.mode_vote_opts = []
        self.mode_votes = {}
        self.vote_locked = False
        self._lock_start = 0

      
    def register(self):
        eh = self.instance.event_handler
        eh.register_event('player_chat', self.on_chat)
        eh.register_event('player_disconnects', self.on_disconnect)
        eh.register_event('new_round', self.on_new_round)

       
    def _can_run(self, pid, cooldown):
        now = time.time()
        last = self.last_cmd_time.get(pid, 0)
        if now - last < cooldown:
            return False, int(cooldown - (now - last))
        self.last_cmd_time[pid] = now
        return True, 0

    def _get_player_count(self):
        """Get current player count - simplified like original"""
        try:
            return len(self.instance.players())
        except:
            return 1

    def on_chat(self, args):
        pid = args.get('player_id')
        player = args.get('player')
        raw_msg = args.get('message', '').strip()
        
        # Only handle commands that start with !
        if not raw_msg.startswith('!'):
            return
            
        msg = raw_msg[1:].lower()
        
        # Block commands during cooldown
        if self.vote_locked and msg in ('rtv', 'rtm'):
            rem = max(0, int(300 - (time.time() - self._lock_start)))  # 5 minute cooldown
            self.instance.tell(pid, f'Wait {rem}s to vote again')
            return
            
        # !maplist pagination
        if msg.startswith('maplist'):
            parts = msg.split()
            if len(parts) == 2 and parts[1] in ('1', '2'):
                maps = self.primary_maps if parts[1] == '1' else self.secondary_maps
                if maps:
                    for i in range(0, len(maps), 5):
                        self.instance.tell(pid, ', '.join(maps[i:i+5]))
                else:
                    self.instance.tell(pid, 'No maps configured')
            else:
                self.instance.tell(pid, 'Usage: !maplist <1|2>')
            return

        # !nominate for RTV
        if msg.startswith('nominate '):
            map_name = msg.split(' ', 1)[1]
            if map_name in self.primary_maps or map_name in self.secondary_maps:
                self.nominations.setdefault(map_name, set()).add(pid)
                self.instance.tell(pid, f'Nominated {map_name}')
            else:
                self.instance.tell(pid, f'Unknown map: {map_name}')
            return

        # !rtv
        if msg == 'rtv' and self.enable_rtv:
            ok, rem = self._can_run(pid, self.rtv_cool_down)
            if not ok:
                self.instance.tell(pid, f'Wait {rem}s to RTV again')
                return
                
            total = self._get_player_count()
            req = max(1, math.ceil(total * self.rtv_percentage / 100))
            
            if pid in self.rtv_votes:
                self.instance.tell(pid, 'Already voted')
            else:
                self.rtv_votes.add(pid)
                self.instance.say(f'{player} wants to rock the vote ({len(self.rtv_votes)}/{req})')
                
                if not self.rtv_active and len(self.rtv_votes) >= req:
                    self.rtv_active = True
                    self._start_rtv_vote()
            return

        # !unrtv
        if msg == 'unrtv' and self.enable_rtv:
            if pid in self.rtv_votes:
                self.rtv_votes.remove(pid)
                total = self._get_player_count()
                req = max(1, math.ceil(total * self.rtv_percentage / 100))
                self.instance.say(f'{player} removed RTV vote ({len(self.rtv_votes)}/{req})')
            else:
                self.instance.tell(pid, 'You have not voted')
            return

        # !modelist
        if msg == 'modelist' and self.enable_rtm:
            if self.rtm_modes:
                for i in range(0, len(self.rtm_modes), 5):
                    self.instance.tell(pid, ', '.join(self.rtm_modes[i:i+5]))
            else:
                self.instance.tell(pid, 'No modes configured')
            return

        # !rtm
        if msg == 'rtm' and self.enable_rtm:
            if len(self.rtm_modes) <= 1:
                self.instance.tell(pid, 'RTM disabled: only one mode available')
                return
                
            ok, rem = self._can_run(pid, self.rtm_cool_down)
            if not ok:
                self.instance.tell(pid, f'Wait {rem}s to RTM again')
                return
                
            total = self._get_player_count()
            req = max(1, math.ceil(total * self.rtm_percentage / 100))
            
            if pid in self.rtm_votes:
                self.instance.tell(pid, 'Already voted')
            else:
                self.rtm_votes.add(pid)
                self.instance.say(f'{player} wants to rock the mode ({len(self.rtm_votes)}/{req})')
                
                if not self.rtm_active and len(self.rtm_votes) >= req:
                    self.rtm_active = True
                    self._start_rtm_vote()
            return

        # !unrtm
        if msg == 'unrtm' and self.enable_rtm:
            if pid in self.rtm_votes:
                self.rtm_votes.remove(pid)
                total = self._get_player_count()
                req = max(1, math.ceil(total * self.rtm_percentage / 100))
                self.instance.say(f'{player} removed RTM vote ({len(self.rtm_votes)}/{req})')
            else:
                self.instance.tell(pid, 'You have not voted')
            return

        # Numeric choice
        if msg.isdigit():
            idx = int(msg) - 1
            if self.rtm_active:
                self._handle_rtm_vote(pid, player, idx)
            elif self.rtv_active:
                self._handle_rtv_vote(pid, player, idx)
            return

    def _start_rtv_vote(self):
        # Build vote options from nominations + random maps
        nominated_maps = list(self.nominations.keys())
        remaining_maps = [m for m in self.primary_maps if m not in nominated_maps]
        
        # Take up to 4 nominated maps, fill remainder from primary maps
        vote_options = nominated_maps[:4]
        if len(vote_options) < 4 and remaining_maps:
            needed = 4 - len(vote_options)
            vote_options.extend(random.sample(remaining_maps, min(needed, len(remaining_maps))))
        
        self.map_vote_opts = vote_options
        self.map_votes = {m: set() for m in self.map_vote_opts}
        
        # Show vote options
        options_text = ', '.join(f'{i+1}:{m}' for i, m in enumerate(self.map_vote_opts))
        self.instance.say(f'Map vote: {options_text}')
        self.instance.say(f'Vote with !<number>. {self.rtv_vote_time}s remaining.')
        
        # Start vote timer
        self.rtv_timer = threading.Timer(self.rtv_vote_time, self._end_rtv)
        self.rtv_timer.daemon = True
        self.rtv_timer.start()

    def _handle_rtv_vote(self, pid, player, idx):
        if not (0 <= idx < len(self.map_vote_opts)):
            self.instance.tell(pid, f'Invalid choice. Use 1-{len(self.map_vote_opts)}')
            return
            
        selected_map = self.map_vote_opts[idx]
        
        # Remove from any existing votes
        for votes in self.map_votes.values():
            votes.discard(pid)
            
        # Add to selected map
        self.map_votes[selected_map].add(pid)
        vote_count = len(self.map_votes[selected_map])
        
        self.instance.say(f'{player} voted for {selected_map} ({vote_count})')

    def _end_rtv(self):
        self.instance.say('RTV vote ended')
        
        total = self._get_player_count()
        req = max(1, math.ceil(total * self.rtv_win_percentage / 100))
        
        # Find winning map
        if not self.map_votes:
            self.instance.say('No votes received')
            self.next_map = None
        else:
            vote_counts = {m: len(votes) for m, votes in self.map_votes.items()}
            max_votes = max(vote_counts.values())
            
            if max_votes < req:
                self.instance.say('Not enough votes to change map')
                self.next_map = None
            else:
                winners = [m for m, count in vote_counts.items() if count == max_votes]
                winner = random.choice(winners)
                self.instance.say(f'Map will change to {winner} next round')
                self.next_map = winner
        
        self._reset_rtv()

    def _reset_rtv(self):
        self.rtv_votes.clear()
        self.rtv_active = False
        if self.rtv_timer:
            self.rtv_timer.cancel()
            self.rtv_timer = None
        self.map_vote_opts = []
        self.map_votes = {}
        self.nominations.clear()

    def _start_rtm_vote(self):
        self.mode_vote_opts = self.rtm_modes[:]
        self.mode_votes = {m: set() for m in self.mode_vote_opts}
        
        # Show vote options
        options_text = ', '.join(f'{i+1}:{m}' for i, m in enumerate(self.mode_vote_opts))
        self.instance.say(f'Mode vote: {options_text}')
        self.instance.say(f'Vote with !<number>. {self.rtm_vote_time}s remaining.')
        
        # Start vote timer
        self.rtm_timer = threading.Timer(self.rtm_vote_time, self._end_rtm)
        self.rtm_timer.daemon = True
        self.rtm_timer.start()

    def _handle_rtm_vote(self, pid, player, idx):
        if not (0 <= idx < len(self.mode_vote_opts)):
            self.instance.tell(pid, f'Invalid choice. Use 1-{len(self.mode_vote_opts)}')
            return
            
        selected_mode = self.mode_vote_opts[idx]
        
        # Remove from any existing votes
        for votes in self.mode_votes.values():
            votes.discard(pid)
            
        # Add to selected mode
        self.mode_votes[selected_mode].add(pid)
        vote_count = len(self.mode_votes[selected_mode])
        
        self.instance.say(f'{player} voted for {selected_mode} ({vote_count})')

    def _end_rtm(self):
        self.instance.say('RTM vote ended')
        
        total = self._get_player_count()
        req = max(1, math.ceil(total * self.rtm_win_percentage / 100))
        
        # Find winning mode
        if not self.mode_votes:
            self.instance.say('No votes received')
            self.next_mode = None
        else:
            vote_counts = {m: len(votes) for m, votes in self.mode_votes.items()}
            max_votes = max(vote_counts.values())
            
            if max_votes < req:
                self.instance.say('Not enough votes to change mode')
                self.next_mode = None
            else:
                winners = [m for m, count in vote_counts.items() if count == max_votes]
                winner = random.choice(winners)
                self.instance.say(f'Mode will change to {winner} next round')
                self.next_mode = winner
        
        self._reset_rtm()

    def _reset_rtm(self):
        self.rtm_votes.clear()
        self.rtm_active = False
        if self.rtm_timer:
            self.rtm_timer.cancel()
            self.rtm_timer = None
        self.mode_vote_opts = []
        self.mode_votes = {}

    def on_new_round(self, args):
        """Handle new round - apply map/mode changes and set cooldown"""
        
        # Apply map change
        if self.next_map:
            current_map = self.instance.map()
            if current_map != self.next_map:
                self.instance.say(f'Changing map to {self.next_map}')
                self.instance.map(self.next_map)
            self.next_map = None
            
            # Set cooldown after map change
            self.vote_locked = True
            self._lock_start = time.time()
            threading.Timer(self.rtv_cool_down, lambda: setattr(self, 'vote_locked', False)).start()

        # Apply mode change  
        if self.next_mode:
            self.instance.say(f'Changing mode to {self.next_mode}')
            self.instance.rcon_exec(f'g_gametype {self.next_mode}')
            self.next_mode = None
            
            # Set cooldown after mode change
            self.vote_locked = True
            self._lock_start = time.time()
            threading.Timer(self.rtm_cool_down, lambda: setattr(self, 'vote_locked', False)).start()

    def on_disconnect(self, args):
        """Remove disconnected player from all votes"""
        pid = args.get('player_id')
        self.rtv_votes.discard(pid)
        self.rtm_votes.discard(pid)
        for votes in self.map_votes.values():
            votes.discard(pid)
        for votes in self.mode_votes.values():
            votes.discard(pid)
