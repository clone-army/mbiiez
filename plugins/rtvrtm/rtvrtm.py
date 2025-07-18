import time
import random
import re
import threading
import math

class plugin:
    """
    RTV & RTM Plugin for MBIIEZ

    Supports:
      - !maplist (1/2) pagination
      - !nominate maps for RTV
      - !rtv / !unrtv voting with percentage threshold
      - map vote with nominations + random fill, same threshold
      - deferred map change at new_round
      - !modelist pagination
      - !rtm / !unrtm voting with percentage threshold
      - RTM vote options from config.rtm_modes
      - deferred mode change at new_round
      - flood protection and post-round cooldown for RTV and RTM
      - periodic prompts and countdown alerts for both votes
      - colored map names & option numbers in red
      - logging of RTV/RTM requests, openings, and successes
    All times in seconds.
    """
    plugin_name = "RTVRTM"
    plugin_author = "Auto-generated"
    plugin_url = ""

    COLOR_RED = '^1'
    COLOR_WHITE = '^7'

    # Mapping of mode names to numeric IDs
    MODE_MAP = {
        'Open': 0,
        'Semi-Authentic': 1,
        'Full-Authentic': 2,
        'Duel': 3,
        'Legends': 4,
    }

    def __init__(self, instance):
        self.instance = instance
        cfg = instance.config.get('plugins', {}).get('rtvrtm', {})
        # General settings
        self.enable_rtv      = cfg.get('enable_rtv', True)
        self.enable_rtm      = cfg.get('enable_rtm', True)
        self.rtv_vote_time   = cfg.get('rtv_vote_time', 30)
        self.rtv_cool_down   = cfg.get('rtv_cool_down', 5)
        self.rtv_percentage  = cfg.get('rtv_percentage', 50) # Needed to call rtv
        self.rtv_win_percentage   = cfg.get('rtv_win_percentage', 50)    # to change map after vote
        self.rtv_prompt_time = cfg.get('rtv_prompt_time', 15)
        self.rtm_vote_time   = cfg.get('rtm_vote_time', 30)
        self.rtm_cool_down   = cfg.get('rtm_cool_down', 5)
        self.rtm_percentage  = cfg.get('rtm_percentage', self.rtv_percentage)
        self.rtm_win_percentage   = cfg.get('rtm_win_percentage', 50)    # to change map after vote
        self.rtm_prompt_time = cfg.get('rtm_prompt_time', self.rtv_prompt_time)
        
        # Flood protection
        self.last_cmd_time = {}
        # Map listings & nomination for RTV
        rtv_cfg = cfg.get('rtv', {})
        self.primary_maps   = rtv_cfg.get('primary_maps', [])
        self.secondary_maps = rtv_cfg.get('secondary_maps', [])
        self.nominations    = {}
        # RTV vote state
        self.rtv_votes       = set()
        self.rtv_active      = False
        self.rtv_timer       = None
        self.rtv_prompt_thr  = None
        self.next_map        = None
        self.map_vote_opts   = []
        self.map_votes       = {}
        # RTM modes and vote state
        self.rtm_modes       = cfg.get('rtm_modes', [])
        self.rtm_votes       = set()
        self.rtm_active      = False
        self.rtm_timer       = None
        self.rtm_prompt_thr  = None
        self.next_mode       = None
        self.mode_vote_opts  = []
        self.mode_votes      = {}
        # Post-round cooldown lock
        self.vote_locked     = False
        self._lock_start     = 0

        if(self.instance.has_plugin("auto_message")):
            # Create dynamic message based on enabled features
            features = []
            if self.enable_rtv:
                features.append("!rtv for map changes")
            if self.enable_rtm:
                features.append("!rtm for mode changes")
            
            if features:
                if len(features) == 1:
                    message = f"This server uses RTVRTM plugin. Type {features[0]}."
                else:
                    message = f"This server uses RTVRTM plugin. Type {' or '.join(features)}."
                
                self.instance.config['plugins']['auto_message']['messages'].append(message)
            else:
                # Both disabled - add a generic message
                self.instance.config['plugins']['auto_message']['messages'].append("This server has RTVRTM plugin installed but voting is currently disabled.")
            
            # Add beta message
            self.instance.config['plugins']['auto_message']['messages'].append("This servers uses a new still in beta re-write of RTVRTM as a plugin for MBIIEZ. Please report any issues on the discord.")

      
    def register(self):
        eh = self.instance.event_handler
        
        #Register both so we capture with ! and without
        eh.register_event('player_chat', self.on_chat)
        eh.register_event('player_chat_command', self.on_chat)  
        
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
        try:
            pl = self.instance.players()
            self.instance.log_handler.log(f"[RTVRTM] Raw players: {pl}")
            self.instance.log_handler.log(f"[RTVRTM] Counted {len(pl)} players from status")
            return len(pl)
        except Exception as e:
            self.instance.log_handler.log(f"[RTVRTM] Failed to get player list: {e}")
            return 1

    def on_chat(self, args):
        pid = args.get('player_id')
        player = args.get('player')
        
        raw_msg = args.get('message', '').strip().lower()
        msg = raw_msg.lstrip('!')        
                
        # Block votes during cooldown
        if self.vote_locked and msg == ('rtv') and self.enable_rtv:
            rem = max(0, int(self.rtv_cool_down - (time.time()-self._lock_start)))
            self.instance.tell(pid, f'Please wait {rem}s as RTV is on cooldown')
            return
            
        # Block votes during cooldown
        if self.vote_locked and msg == ('rtm') and self.enable_rtm:
            rem = max(0, int(self.rtm_cool_down - (time.time()-self._lock_start)))
            self.instance.tell(pid, f'Please wait {rem}s as RTM is on cooldown')
            return            
            
        # !maplist pagination
        if msg.startswith('maplist') and self.enable_rtv:
            parts = msg.split()
            if len(parts)==2 and parts[1] in ('1','2'):
                lst = self.primary_maps if parts[1]=='1' else self.secondary_maps
                for i in range(0,len(lst),5):
                    self.instance.tell(pid,', '.join(lst[i:i+5]))
            else:
                self.instance.tell(pid,'Usage: !maplist <1|2>')
            return

        # !nominate for RTV
        if msg.startswith('nominate ') and self.enable_rtv:
            m = msg.split(' ',1)[1]
            if m in self.primary_maps or m in self.secondary_maps:
                self.nominations.setdefault(m,set()).add(pid)
                self.instance.tell(pid,f'Nominated {self.COLOR_RED}{m}{self.COLOR_WHITE}')
            else:
                self.instance.tell(pid,f'Unknown map: {m}')
            return

        # !unrtv
        if msg == ('unrtv') and self.enable_rtv:
            total=self._get_player_count()
            req=max(1,math.ceil(total*self.rtv_percentage/100))
            if pid in self.rtv_votes:
                self.rtv_votes.remove(pid)
                self.instance.say(f'{player}{self.COLOR_WHITE} removed RTV vote ({len(self.rtv_votes)}/{req})')
            else:
                self.instance.tell(pid,'You have not RTV-voted')
            return

        # !rtv
        if msg == ('rtv') and self.enable_rtv:
            ok,rem=self._can_run(pid,self.rtv_cool_down)
            if not ok:
                self.instance.tell(pid,f'Wait {rem}s to RTV again')
                return
            total=self._get_player_count();req=max(1,math.ceil(total*self.rtv_percentage/100))
            if pid in self.rtv_votes:
                self.instance.tell(pid,'Already RTV-voted')
            else:
                self.instance.log_handler.log(f'RTV requested by {player}')
                self.rtv_votes.add(pid)
                self.instance.say(f'{player}{self.COLOR_WHITE} wants to rock the vote ({self.COLOR_RED}{len(self.rtv_votes)}/{req}{self.COLOR_WHITE})')
                if not self.rtv_active and len(self.rtv_votes)>=req:
                    self.rtv_active=True
                    self.instance.log_handler.log('RTV threshold reached, starting map vote')
                    self._start_rtv_vote()
            return

        # !modelist pagination
        if msg.startswith('modelist') and self.enable_rtm:
            lst=self.rtm_modes
            for i in range(0,len(lst),5):
                self.instance.tell(pid,', '.join(lst[i:i+5]))
            return

        # !unrtm
        if msg == ('unrtm') and self.enable_rtm:
            total=self._get_player_count();req=max(1,math.ceil(total*self.rtm_percentage/100))
            if pid in self.rtm_votes:
                self.rtm_votes.remove(pid)
                self.instance.say(f'{player}{self.COLOR_WHITE} removed RTM vote ({len(self.rtm_votes)}/{req})')
            else:
                self.instance.tell(pid,'You have not RTM-voted')
            return

        # !rtm
        if msg == ('rtm') and self.enable_rtm:
            if len(self.rtm_modes)<=1:
                return
            ok,rem=self._can_run(pid,self.rtm_cool_down)
            if not ok:
                self.instance.tell(pid,f'Wait {rem}s to RTM again')
                return
            total=self._get_player_count();req=max(1,math.ceil(total*self.rtm_percentage/100))
            if pid in self.rtm_votes:
                self.instance.tell(pid,'Already RTM-voted')
            else:
                self.instance.log_handler.log(f'RTM requested by {player}')
                self.rtm_votes.add(pid)
                self.instance.say(f'{player}{self.COLOR_WHITE} wants to rock the mode ({self.COLOR_RED}{len(self.rtm_votes)}/{req}{self.COLOR_WHITE})')
                if not self.rtm_active and len(self.rtm_votes)>=req:
                    self.rtm_active=True
                    self.instance.log_handler.log('RTM threshold reached, starting mode vote')
                    self._start_rtm_vote()
            return

        # numeric choice: prioritize RTM if active, else RTV
        if re.fullmatch(r'\d+', msg):
            idx = int(msg) - 1
            if self.rtm_active:
                self._handle_rtm_vote(pid, player, idx)
            elif self.rtv_active:
                self._handle_rtv_vote(pid, player, idx)
            return

    def _start_rtv_vote(self):
        sorted_noms = sorted(self.nominations.items(), key=lambda kv: len(kv[1]), reverse=True)
        opts = [m for m, _ in sorted_noms]

        if len(opts) < 4:
            pool = [m for m in self.primary_maps if m not in opts]
            opts += random.sample(pool, 4 - len(opts))

        opts = opts[:4]
        opts.append("Do not change")  # Add "Do Not Change" option

        self.map_vote_opts = opts
        self.map_votes = {m: set() for m in self.map_vote_opts}

        opts_str = ', '.join(
            f'{self.COLOR_RED}{i+1}{self.COLOR_WHITE}:{"Do not change" if m == "Do not change" else m}'
            for i, m in enumerate(self.map_vote_opts)
        )
        self.instance.say(f'Map vote started! Options: {opts_str}')
        self.instance.say(f'Vote with !<number>. Ends in {self.rtv_vote_time}s.')

        self.rtv_timer = threading.Timer(self.rtv_vote_time, self._end_rtv)
        self.rtv_timer.daemon = True
        self.rtv_timer.start()
        threading.Thread(target=self._prompt_rtv).start()
        for sec in (20, 10, 5):
            threading.Timer(self.rtv_vote_time - sec,
                            lambda s=sec: self.instance.say(f'{self.COLOR_RED}Vote ends in {s}s{self.COLOR_WHITE}')
                            ).start()

    def _prompt_rtv(self):
        start=time.time()
        while self.rtv_active:
            if time.time()-start>=self.rtv_vote_time: break
            time.sleep(self.rtv_prompt_time)
            if self.rtv_active:
                opts_str=', '.join(f'{self.COLOR_RED}{i+1}{self.COLOR_WHITE}:{m}' for i,m in enumerate(self.map_vote_opts))
                self.instance.say(f'Reminder: {opts_str}')

    def _handle_rtv_vote(self, pid, player, idx):
        if not (0 <= idx < len(self.map_vote_opts)):
            self.instance.tell(pid, f'Invalid choice 1-{len(self.map_vote_opts)}')
            return

        m = self.map_vote_opts[idx]

        # Remove player from all existing votes
        for mv in self.map_votes.values():
            mv.discard(pid)

        self.map_votes[m].add(pid)

        # Check if they previously voted (for messaging)
        if any(pid in v for v in self.map_votes.values() if v is not self.map_votes[m]):
            self.instance.tell(pid, f'You changed your vote to {self.COLOR_RED}{m}{self.COLOR_WHITE} ({len(self.map_votes[m])})')
        else:
            self.instance.tell(pid, f'You voted for {self.COLOR_RED}{m}{self.COLOR_WHITE} ({len(self.map_votes[m])})')

    def _end_rtv(self):
        self.instance.say(f'RTV closed with {len(self.rtv_votes)} votes')
        total = self._get_player_count()
        req = max(1, math.ceil(total * self.rtv_win_percentage / 100))
        counts = {m: len(v) for m, v in self.map_votes.items()}

        if not counts or max(counts.values()) < req:
            self.instance.say('Not enough map votes; failed')
            self.next_map = None
        else:
            maxv = max(counts.values())
            w = [m for m, c in counts.items() if c == maxv]
            winner = random.choice(w)

            if winner == "Do not change":
                self.instance.say("Majority voted to keep current map.")
                self.next_map = None
            else:
                self.instance.log_handler.log(f'Map vote success: {winner}')
                self.instance.say(f'Changing map to {self.COLOR_RED}{winner}{self.COLOR_WHITE} next round')
                self.next_map = winner

        self._reset_rtv()


    def _reset_rtv(self):
        self.rtv_votes.clear();self.rtv_active=False
        if self.rtv_timer: self.rtv_timer.cancel(); self.rtv_timer=None
        self.map_vote_opts=[];self.map_votes={};self.nominations.clear()

    def _start_rtm_vote(self):
        self.mode_vote_opts = self.rtm_modes[:]
        self.mode_vote_opts.append("Do not change")
        self.mode_votes = {m: set() for m in self.mode_vote_opts}

        opts_str = ', '.join(
            f'{self.COLOR_RED}{i+1}{self.COLOR_WHITE}:{"Do not change" if m == "Do not change" else m}'
            for i, m in enumerate(self.mode_vote_opts)
        )
        self.instance.say(f'Mode vote started! Options: {opts_str}')
        self.instance.say(f'Vote with !<number>. Ends in {self.rtm_vote_time}s.')

        self.rtm_timer = threading.Timer(self.rtm_vote_time, self._end_rtm)
        self.rtm_timer.daemon = True
        self.rtm_timer.start()
        threading.Thread(target=self._prompt_rtm).start()
        for sec in (20, 10, 5):
            threading.Timer(self.rtm_vote_time - sec,
                            lambda s=sec: self.instance.say(f'{self.COLOR_RED}Mode vote ends in {s}s{self.COLOR_WHITE}')
                            ).start()


    def _prompt_rtm(self):
        start=time.time()
        while self.rtm_active:
            if time.time()-start>=self.rtm_vote_time: break
            time.sleep(self.rtm_prompt_time)
            if self.rtm_active:
                opts_str=', '.join(f'{self.COLOR_RED}{i+1}{self.COLOR_WHITE}:{m}' for i,m in enumerate(self.mode_vote_opts))
                self.instance.say(f'Reminder: {opts_str}')

    def _handle_rtm_vote(self, pid, player, idx):
        if not (0 <= idx < len(self.mode_vote_opts)):
            self.instance.tell(pid, f'Invalid choice 1-{len(self.mode_vote_opts)}')
            return

        m = self.mode_vote_opts[idx]

        for v in self.mode_votes.values():
            v.discard(pid)

        self.mode_votes[m].add(pid)

        if any(pid in v for v in self.mode_votes.values() if v is not self.mode_votes[m]):
            self.instance.say(f'{player}{self.COLOR_WHITE} changed their vote to {self.COLOR_RED}{m}{self.COLOR_WHITE} ({len(self.mode_votes[m])})')
        else:
            self.instance.say(f'{player}{self.COLOR_WHITE} voted for {self.COLOR_RED}{m}{self.COLOR_WHITE} ({len(self.mode_votes[m])})')
            
        
    def _end_rtm(self):
        self.instance.say(f'RTM closed with {len(self.rtm_votes)} votes')
        total = self._get_player_count()
        req = max(1, math.ceil(total * self.rtm_win_percentage / 100))
        counts = {m: len(v) for m, v in self.mode_votes.items()}

        if not counts or max(counts.values()) < req:
            self.instance.say('Not enough mode votes; failed')
            self.next_mode = None
        else:
            maxv = max(counts.values())
            w = [m for m, c in counts.items() if c == maxv]
            winner = random.choice(w)

            if winner == "Do not change":
                self.instance.say("Majority voted to keep current mode.")
                self.next_mode = None
            else:
                self.instance.say(f'Changing mode to {self.COLOR_RED}{winner}{self.COLOR_WHITE} next round')
                self.next_mode = winner

        self._reset_rtm()


    def _reset_rtm(self):
        self.rtm_votes.clear();self.rtm_active=False
        if self.rtm_timer: self.rtm_timer.cancel(); self.rtm_timer=None
        self.mode_vote_opts=[];self.mode_votes={}

    def on_new_round(self,args):


        # Re-Set the CVAR
        code = (1928 if self.enable_rtv else 0) + (2000 if self.enable_rtm else 0)
        #self.instance.console.rcon(f"sets RTVRTM {code}/1234")        
        cmd = "sets RTVRTM 1928/3.6b"
        self.instance.console.rcon(str(cmd), False)

        # apply map change
        if self.next_map:
        
            if self.instance.map() == self.next_map:
                self.next_map=None
                return
        
            self.instance.say(f'Changing map to {self.COLOR_RED}{self.next_map}{self.COLOR_WHITE} now')
            
            self.instance.map(self.next_map)
           
            # lock voting
            self.vote_locked=True;self._lock_start=time.time()
            threading.Timer(self.rtv_cool_down, lambda: setattr(self,'vote_locked',False)).start() 
            
            self.next_map=None
        # apply mode change
        if self.next_mode:
            num=str(self.MODE_MAP.get(self.next_mode))
            if num is not None:
                self.instance.say(f'Changing mode to {self.COLOR_RED}{self.next_mode}{self.COLOR_WHITE} now')
     
                self.instance.mode(num)
                # lock voting
                self.vote_locked=True;self._lock_start=time.time()
                threading.Timer(self.rtm_cool_down, lambda: setattr(self,'vote_locked',False)).start()     
                    
            self.next_mode=None

    def on_disconnect(self,args):
        pid=args.get('player_id')
        self.rtv_votes.discard(pid)
        self.rtm_votes.discard(pid)
        for v in self.map_votes.values(): v.discard(pid)
        for v in self.mode_votes.values(): v.discard(pid)
