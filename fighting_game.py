import pygame
import random
import math
import pickle
import os

# --- INITIALIZATION ---
pygame.init()
WIDTH, HEIGHT = 1200, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Adaptive AI Fighter: Q-Learning Edition")
clock = pygame.time.Clock()
FPS = 60

# --- COLORS ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 50, 50)
BLUE = (50, 50, 200)
GREEN = (50, 200, 50)
YELLOW = (255, 255, 0)
GRAY = (100, 100, 100)
ORANGE = (255, 165, 0)

# --- GAME CONSTANTS ---
GRAVITY = 0.8
FLOOR_Y = HEIGHT - 50
PLAYER_WIDTH, PLAYER_HEIGHT = 50, 100
SPEED = 5
JUMP_FORCE = -22 
ATTACK_COOLDOWN = 30 
SHIELD_MAX = 100
SHIELD_REGEN = 0.5
SHIELD_DRAIN = 2
SHOOT_DAMAGE = 40

# Ranges for logic
PUNCH_RANGE = 40
KICK_RANGE = 60 # Kick range is longer

# --- Q-LEARNING CONSTANTS ---
ACTIONS = ["LEFT", "RIGHT", "JUMP", "PUNCH", "KICK", "SHIELD", "SHOOT", "IDLE"]

# --- HELPER FUNCTIONS ---
def draw_text(text, size, color, x, y, align="center"):
    font = pygame.font.SysFont("arial", size, bold=True)
    render = font.render(text, True, color)
    rect = render.get_rect()
    if align == "center":
        rect.center = (x, y)
    elif align == "left":
        rect.topleft = (x, y)
    screen.blit(render, rect)

class SpriteAnimator:
    def __init__(self, character_name, scale_factor=3.0):
        self.character_name = character_name
        self.scale = scale_factor
        self.animation_list = {} 
        self.frame_index = 0
        self.action = "Idle" 
        self.update_time = pygame.time.get_ticks()
        self.cooldown = 80 # Faster animation speed
        
        actions = ["Idle", "Run", "Jump", "Punch", "Kick", "Shield", "Hurt", "Shoot"]
        
        for action in actions:
            temp_list = []
            for i in range(10):
                try:
                    img_path = f"assets/{character_name}/{action}/{i}.png"
                    img = pygame.image.load(img_path).convert_alpha()
                    w = int(img.get_width() * self.scale)
                    h = int(img.get_height() * self.scale)
                    img = pygame.transform.scale(img, (w, h))
                    temp_list.append(img)
                except FileNotFoundError:
                    break 
            self.animation_list[action] = temp_list

    def get_state(self, fighter):
        if fighter.is_shielding: return "Shield"
        if fighter.shoot_anim_frame > 0: return "Shoot"
        if fighter.is_attacking:
            if fighter.attack_type == "punch": return "Punch"
            if fighter.attack_type == "kick": return "Kick"
        if fighter.vel_y != 0: return "Jump"
        
        keys = pygame.key.get_pressed()
        if not fighter.is_ai and (keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]):
            return "Run"
        return "Idle"

    def update(self, fighter):
        new_action = self.get_state(fighter)
        if new_action != self.action:
            self.action = new_action
            self.frame_index = 0
            self.update_time = pygame.time.get_ticks()

        current_animation = self.animation_list.get(self.action, self.animation_list["Idle"])
        if not current_animation: return

        if pygame.time.get_ticks() - self.update_time > self.cooldown:
            self.frame_index += 1
            self.update_time = pygame.time.get_ticks()
            if self.frame_index >= len(current_animation):
                if self.action in ["Punch", "Kick", "Shoot", "Jump"]:
                     self.frame_index = len(current_animation) - 1
                else:
                     self.frame_index = 0 

    def draw(self, surface, fighter):
        current_animation = self.animation_list.get(self.action, self.animation_list["Idle"])
        if not current_animation: 
            pygame.draw.rect(surface, fighter.color, fighter.rect)
            return

        image = current_animation[self.frame_index]
        if fighter.direction == -1:
            image = pygame.transform.flip(image, True, False)

        sprite_rect = image.get_rect()
        sprite_rect.centerx = fighter.rect.centerx
        sprite_rect.bottom = fighter.rect.bottom 
        surface.blit(image, sprite_rect)

class Projectile:
    sprite = None 
    def __init__(self, x, y, direction, owner_color):
        self.rect = pygame.Rect(x, y, 20, 10)
        self.direction = direction
        self.speed = 15
        self.color = owner_color
        self.active = True
        if Projectile.sprite is None:
            try:
                img = pygame.image.load("assets/dot.png").convert_alpha()
                Projectile.sprite = pygame.transform.scale(img, (30, 30))
            except FileNotFoundError:
                Projectile.sprite = None

    def update(self):
        self.rect.x += self.speed * self.direction
        if self.rect.x < 0 or self.rect.x > WIDTH:
            self.active = False

    def draw(self, surface):
        if Projectile.sprite:
            img_rect = Projectile.sprite.get_rect()
            img_rect.center = self.rect.center
            surface.blit(Projectile.sprite, img_rect)
        else:
             pygame.draw.rect(surface, self.color, self.rect)
             pygame.draw.circle(surface, YELLOW, self.rect.center, 8)

class Fighter:
    def __init__(self, x, y, color, is_ai=False):
        self.rect = pygame.Rect(x, y, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.color = color
        self.is_ai = is_ai
        self.shoot_anim_frame = 0
        char_name = "Villain" if is_ai else "Hero" 
        self.animator = SpriteAnimator(char_name, scale_factor=0.5)

        self.vel_y = 0
        self.direction = 1 
        self.health = 100
        self.is_attacking = False
        self.attack_type = None 
        self.attack_frame = 0
        self.has_hit = False 
        self.is_shielding = False
        self.shield_gauge = SHIELD_MAX
        self.shield_cooldown = 0
        self.has_shot = False 
        self.projectile = None
        self.last_attack_time = 0
        self.combo_count = 0

    def move(self, dx, dy):
        self.rect.x += dx
        self.rect.y += dy
        if self.rect.left < 0: self.rect.left = 0
        if self.rect.right > WIDTH: self.rect.right = WIDTH

    def apply_gravity(self):
        self.vel_y += GRAVITY
        self.rect.y += self.vel_y
        if self.rect.bottom >= FLOOR_Y:
            self.rect.bottom = FLOOR_Y
            self.vel_y = 0

    def jump(self):
        if self.rect.bottom == FLOOR_Y:
            self.vel_y = JUMP_FORCE

    def attack(self, type_str, target):
        if self.is_attacking or self.is_shielding: return
        self.is_attacking = True
        self.has_hit = False 
        self.attack_type = type_str
        self.attack_frame = 20 
        current_time = pygame.time.get_ticks()
        if current_time - self.last_attack_time < 800: 
            self.combo_count = min(self.combo_count + 1, 3)
        else:
            self.combo_count = 1
        self.last_attack_time = current_time

    def shoot(self):
        if not self.has_shot and not self.is_attacking and not self.is_shielding:
            self.has_shot = True
            self.shoot_anim_frame = 20
            start_x = self.rect.right if self.direction == 1 else self.rect.left
            self.projectile = Projectile(start_x, self.rect.centery, self.direction, self.color)
            return True
        return False

    def toggle_shield(self, active):
        if self.shield_cooldown > 0:
            self.is_shielding = False
            return
        if active and self.shield_gauge > 0:
            self.is_shielding = True
            self.shield_gauge -= SHIELD_DRAIN
            if self.shield_gauge <= 0:
                self.is_shielding = False
                self.shield_cooldown = 180 
        else:
            self.is_shielding = False
            if self.shield_gauge < SHIELD_MAX:
                self.shield_gauge += SHIELD_REGEN

    def update(self):
        self.apply_gravity()
        if self.shoot_anim_frame > 0: self.shoot_anim_frame -= 1
        if self.shield_cooldown > 0: self.shield_cooldown -= 1

        hitbox = None
        if self.is_attacking:
            self.attack_frame -= 1
            if 10 < self.attack_frame < 18:
                reach = PUNCH_RANGE if self.attack_type == "punch" else KICK_RANGE
                if self.combo_count == 3: reach += 20
                hb_x = self.rect.right if self.direction == 1 else self.rect.left - reach
                hitbox = pygame.Rect(hb_x, self.rect.y + 10, reach, 50)
            if self.attack_frame <= 0:
                self.is_attacking = False
                self.attack_type = None

        if self.projectile:
            self.projectile.update()
            if not self.projectile.active:
                self.projectile = None
        if hasattr(self, 'animator'):
            self.animator.update(self)
        return hitbox

    def take_damage(self, amount, is_unblockable=False):
        if self.is_shielding and not is_unblockable:
            self.shield_gauge -= amount * 2
            return False 
        else:
            self.health -= amount
            return True 

    def draw(self, surface):
        if hasattr(self, 'animator'):
            self.animator.draw(surface, self)
        # if self.is_shielding:
        #     pygame.draw.circle(surface, (100, 200, 255), self.rect.center, 70, 4)
        # if self.projectile:
        #     self.projectile.draw(surface)
        # pygame.draw.rect(surface, RED, (self.rect.x, self.rect.y - 20, 50, 5))
        # pygame.draw.rect(surface, GREEN, (self.rect.x, self.rect.y - 20, 50 * (self.health/100), 5))
        # pygame.draw.rect(surface, BLUE, (self.rect.x, self.rect.y - 10, 50 * (self.shield_gauge/SHIELD_MAX), 3))


# --- CLASS: INTELLIGENT AI BRAIN ---
# --- CLASS: INTELLIGENT AI BRAIN ---
class VillainBrain:
    def __init__(self, difficulty):
        self.q_table = {} 
        self.difficulty = difficulty
        
        # Hyperparameters
        self.learning_rate = 0.1
        self.discount_factor = 0.95
        
        # Exploration vs Exploitation
        # Hard mode explores less, relies on seeded logic more
        if self.difficulty == "Easy": self.epsilon = 0.3
        elif self.difficulty == "Medium": self.epsilon = 0.15
        else: self.epsilon = 0.05 

        self.last_state = None
        self.last_action = None
        
        # Learning Flags (Easy Mode starts dumb)
        self.knows_shoot = False
        self.knows_kick = False
        if self.difficulty != "Easy":
            self.knows_shoot = True
            self.knows_kick = True
        
        self.current_action_lock = 0
        
        # We call this to fill Q-table with initial "common sense"
        self.pre_seed_logic()

    def pre_seed_logic(self):
        # We iterate through possible states and assign high values to "Smart" moves
        # This gives the Q-Table a head start so it doesn't act randomly at first.
        
        distances = ["CLOSE", "MID", "FAR"]
        verticals = ["GROUND", "AIR"]
        enemy_acts = ["IDLE", "ATTACK", "SHIELD", "PROJECTILE"]
        can_shields = ["YES", "NO"]

        for d in distances:
            for v in verticals:
                for e in enemy_acts:
                    for s in can_shields:
                        state = (d, v, e, s)
                        self.q_table[state] = {a: 0.0 for a in ACTIONS}
                        
                        # --- UNIVERSAL LOGIC (Don't be stupid) ---
                        if e == "PROJECTILE" and s == "YES":
                            self.q_table[state]["SHIELD"] = 5.0
                            self.q_table[state]["JUMP"] = 4.0
                        
                        # --- EASY HEURISTICS ---
                        if self.difficulty == "Easy":
                            if e == "ATTACK" and s == "YES":
                                self.q_table[state]["SHIELD"] = 2.0 # blocks sometimes
                            if d == "CLOSE" and e == "IDLE":
                                self.q_table[state]["PUNCH"] = 3.0
                            if d == "FAR":
                                self.q_table[state]["LEFT"] = 1.0 # Wanders
                                self.q_table[state]["RIGHT"] = 1.0

                        # --- MEDIUM HEURISTICS (Defensive/Poker) ---
                        elif self.difficulty == "Medium":
                            if e == "ATTACK":
                                if s == "YES": self.q_table[state]["SHIELD"] = 8.0 # Strong Defense
                                else: self.q_table[state]["JUMP"] = 5.0 # Evasion
                            
                            if d == "MID" and e == "IDLE":
                                self.q_table[state]["KICK"] = 4.0 # Uses range
                            
                            if d == "CLOSE" and e == "IDLE":
                                self.q_table[state]["PUNCH"] = 3.0 
                                self.q_table[state]["SHIELD"] = 2.0 # Turtle

                        # --- HARD HEURISTICS (Aggressive/Punisher) ---
                        elif self.difficulty == "Hard":
                            if e == "PROJECTILE":
                                self.q_table[state]["SHIELD"] = 10.0 # Perfect block
                            
                            if v == "AIR": # Anti-Air logic
                                self.q_table[state]["KICK"] = 6.0 # Intercept jump
                            
                            if d == "CLOSE":
                                self.q_table[state]["PUNCH"] = 8.0 # Aggressive combo
                            
                            if d == "FAR":
                                self.q_table[state]["SHOOT"] = 5.0 # Zoning
                                self.q_table[state]["PUNCH"] = 4.0 # Dash in (movement)

    def get_state(self, ai: Fighter, player: Fighter):
        # 1. Horizontal Distance (Aligned with Hitbox Constants)
        dist_x = abs(ai.rect.centerx - player.rect.centerx)
        
        if dist_x < PUNCH_RANGE + 10: dist_bucket = "CLOSE"
        elif dist_x < KICK_RANGE + 20: dist_bucket = "MID"
        else: dist_bucket = "FAR"
        
        # 2. Vertical Distance
        if player.rect.bottom < ai.rect.centery: vert_bucket = "AIR"
        else: vert_bucket = "GROUND"

        # 3. Enemy Action
        enemy_act = "IDLE"
        if player.projectile and player.projectile.active:
            # Check if projectile is actually a threat (moving towards AI)
            proj = player.projectile
            if (proj.direction == 1 and proj.rect.x < ai.rect.x) or \
               (proj.direction == -1 and proj.rect.x > ai.rect.x):
                enemy_act = "PROJECTILE"
        elif player.is_attacking: enemy_act = "ATTACK"
        elif player.is_shielding: enemy_act = "SHIELD"

        # 4. Can AI Shield?
        can_shield = "YES" if ai.shield_cooldown == 0 else "NO"
        
        return (dist_bucket, vert_bucket, enemy_act, can_shield)

    def choose_action(self, state, ai_fighter, player_fighter):
        # Unpack state for physics checks
        dist_bucket, vert_bucket, enemy_act, can_shield = state
        
        # Start with all actions
        valid_actions = ACTIONS.copy()

        # --- PHYSICS FILTERS (The Anti-Spam Fix) ---
        # These rules prevent the AI from doing physically impossible/stupid things
        
        # 1. Distance Filters
        dist_x = abs(ai_fighter.rect.centerx - player_fighter.rect.centerx)
        
        # REMOVE PUNCH if too far (Prevents punching air)
        if dist_x > PUNCH_RANGE + 10:
            if "PUNCH" in valid_actions: valid_actions.remove("PUNCH")
            
        # REMOVE KICK if too far
        if dist_x > KICK_RANGE + 20:
             if "KICK" in valid_actions: valid_actions.remove("KICK")

        # 2. Cooldown Filters
        if can_shield == "NO" and "SHIELD" in valid_actions:
            valid_actions.remove("SHIELD")

        # --- DIFFICULTY FILTERS ---
        
        if self.difficulty == "Easy":
            # Easy mode doesn't know complex moves yet
            if not self.knows_kick and "KICK" in valid_actions: valid_actions.remove("KICK")
            if not self.knows_shoot and "SHOOT" in valid_actions: valid_actions.remove("SHOOT")
            
            # Easy mode shouldn't react perfectly to projectiles
            if enemy_act == "PROJECTILE" and random.random() > 0.3:
                 if "SHIELD" in valid_actions: valid_actions.remove("SHIELD")

        elif self.difficulty == "Medium":
            # Medium is passive. If player is far, Medium rarely shoots, prefers to wait.
            if dist_bucket == "FAR" and "SHOOT" in valid_actions and random.random() > 0.3:
                 valid_actions.remove("SHOOT")

        # --- SELECTION ---
        
        # Exploration (Randomness)
        if random.uniform(0, 1) < self.epsilon:
            if not valid_actions: return "IDLE"
            return random.choice(valid_actions)
        
        # Exploitation (Q-Table)
        if state not in self.q_table:
            # If state is new, default to a safe action based on distance
            if not valid_actions: return "IDLE"
            return random.choice(valid_actions)
        
        # Get best action ONLY from the valid list
        # This ensures that even if Q-table says "Punch", we won't do it if we are far away.
        sorted_actions = sorted(self.q_table[state].items(), key=lambda item: item[1], reverse=True)
        
        for action, score in sorted_actions:
            if action in valid_actions:
                return action
        
        return "IDLE" # Fallback

    def learn_trigger(self, trigger_type):
        if self.difficulty == "Easy":
            if trigger_type == "GOT_SHOT":
                self.knows_shoot = True
            if trigger_type == "GOT_KICKED":
                self.knows_kick = True

    def update_q_table(self, state, action, reward, next_state):
        if state not in self.q_table: self.q_table[state] = {a: 0.0 for a in ACTIONS}
        if next_state not in self.q_table: self.q_table[next_state] = {a: 0.0 for a in ACTIONS}

        old_value = self.q_table[state][action]
        next_max = max(self.q_table[next_state].values())
        
        new_value = old_value + self.learning_rate * (reward + self.discount_factor * next_max - old_value)
        self.q_table[state][action] = new_value

# --- MAIN GAME LOOP ---

def main():
    running = True
    in_menu = True
    game_over = False
    
    player = Fighter(200, FLOOR_Y - PLAYER_HEIGHT, BLUE)
    villain = Fighter(600, FLOOR_Y - PLAYER_HEIGHT, RED, is_ai=True)
    villain.direction = -1
    
    brain = None
    difficulty_selected = ""
    winner = ""

    while running:
        clock.tick(FPS)
        screen.fill(BLACK)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if in_menu:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        difficulty_selected = "Easy"
                        brain = VillainBrain("Easy")
                        in_menu = False
                    elif event.key == pygame.K_2:
                        difficulty_selected = "Medium"
                        brain = VillainBrain("Medium")
                        in_menu = False
                    elif event.key == pygame.K_3:
                        difficulty_selected = "Hard"
                        brain = VillainBrain("Hard")
                        in_menu = False
            
            elif game_over:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        player = Fighter(200, FLOOR_Y - PLAYER_HEIGHT, BLUE)
                        villain = Fighter(600, FLOOR_Y - PLAYER_HEIGHT, RED, is_ai=True)
                        villain.direction = -1
                        brain.last_state = None
                        game_over = False
                        winner = ""
                    if event.key == pygame.K_m:
                        in_menu = True

        if in_menu:
            draw_text("ADAPTIVE FIGHTER", 60, WHITE, WIDTH//2, 100)
            draw_text("1. EASY (Learns moves as you use them)", 25, GREEN, WIDTH//2, 280)
            draw_text("2. MEDIUM (Standard Fighter)", 25, YELLOW, WIDTH//2, 330)
            draw_text("3. HARD (Aggressive Master)", 25, RED, WIDTH//2, 380)
            pygame.display.flip()
            continue

        if not game_over:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]: 
                player.move(-SPEED, 0)
                player.direction = -1
            if keys[pygame.K_RIGHT]: 
                player.move(SPEED, 0)
                player.direction = 1
            if keys[pygame.K_UP]: player.jump()
            if keys[pygame.K_a]: player.attack("punch", villain)
            if keys[pygame.K_d]: player.attack("kick", villain)
            if keys[pygame.K_s]: player.shoot()
            player.toggle_shield(keys[pygame.K_w])

            # --- AI LOGIC ---
            current_state = brain.get_state(villain, player)
            
            if brain.current_action_lock <= 0:
                # Pass the fighter objects so the brain can check distance!
                action = brain.choose_action(current_state, villain, player)
                brain.last_action = action
                brain.last_state = current_state
                
                # Dynamic Lock: Move actions are fast, Attacks commit you
                if action in ["PUNCH", "KICK", "SHOOT"]:
                    brain.current_action_lock = 25 # Commit to animation
                else:
                    brain.current_action_lock = 5 # React faster if moving
            else:
                action = brain.last_action
                brain.current_action_lock -= 1
                
            villain.toggle_shield(False)
            
            if action == "LEFT": 
                villain.move(-SPEED, 0)
                villain.direction = -1
            elif action == "RIGHT": 
                villain.move(SPEED, 0)
                villain.direction = 1
            elif action == "JUMP": villain.jump()
            elif action == "PUNCH": villain.attack("punch", player)
            elif action == "KICK": villain.attack("kick", player)
            elif action == "SHIELD": villain.toggle_shield(True)
            elif action == "SHOOT": villain.shoot()
            
            if player.rect.centerx < villain.rect.centerx: villain.direction = -1
            else: villain.direction = 1

            p_hitbox = player.update()
            v_hitbox = villain.update()

            # --- PHYSICS: NO OVERLAP ---
            if player.rect.colliderect(villain.rect):
                push_strength = 5
                if player.rect.centerx < villain.rect.centerx:
                    player.rect.centerx -= push_strength
                    villain.rect.centerx += push_strength
                else:
                    player.rect.centerx += push_strength
                    villain.rect.centerx -= push_strength

            # --- REWARD SYSTEM (THE BRAIN) ---
            step_reward = -0.1 

            # 1. Did AI Whiff? (Miss an attack completely) -> STOP SPAMMING
            if action in ["PUNCH", "KICK"] and not v_hitbox:
                # If we punched air, small penalty
                 step_reward -= 0.5
            elif action in ["PUNCH", "KICK"] and v_hitbox:
                # We launched an attack hitbox... did it hit?
                if v_hitbox.colliderect(player.rect):
                     pass # Handled below
                else:
                     step_reward -= 2.0 # Huge penalty for missing attack (Spacing)

            # 2. Player hits AI
            if p_hitbox and p_hitbox.colliderect(villain.rect) and not player.has_hit:
                player.has_hit = True
                dmg = 8 if player.attack_type == "punch" else 5
                if player.combo_count == 3: dmg *= 2
                
                if player.attack_type == "kick": brain.learn_trigger("GOT_KICKED")

                if villain.take_damage(dmg):
                    step_reward -= 10.0 
                else:
                    step_reward += 5.0 # Blocked

            # 3. Player Shoot hits AI
            if player.projectile and player.projectile.rect.colliderect(villain.rect):
                player.projectile.active = False
                brain.learn_trigger("GOT_SHOT")
                
                if villain.take_damage(SHOOT_DAMAGE, is_unblockable=False):
                     step_reward -= 15.0
                else:
                     step_reward += 10.0

            # 4. AI hits Player
            if v_hitbox and v_hitbox.colliderect(player.rect) and not villain.has_hit:
                villain.has_hit = True
                dmg = 8 if villain.attack_type == "punch" else 5
                if player.take_damage(dmg):
                    step_reward += 10.0 
                else:
                    step_reward -= 1.0 # Blocked

            # 5. AI Shoot hits Player
            if villain.projectile and villain.projectile.rect.colliderect(player.rect):
                player.take_damage(SHOOT_DAMAGE, is_unblockable=True)
                villain.projectile.active = False
                step_reward += 20.0 

            next_state = brain.get_state(villain, player)
            brain.update_q_table(brain.last_state, brain.last_action, step_reward, next_state)

            if player.health <= 0:
                winner = "VILLAIN WINS"
                game_over = True
            elif villain.health <= 0:
                winner = "PLAYER WINS"
                game_over = True

        screen.blit(bg, (0, 0))

        player.draw(screen)
        villain.draw(screen)

        draw_text(f"P1: {int(player.health)}", 20, WHITE, 100, 30)
        draw_text(f"AI: {int(villain.health)}", 20, WHITE, WIDTH-100, 30)
        
        if game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(150)
            overlay.fill(BLACK)
            screen.blit(overlay, (0,0))
            draw_text(winner, 60, GREEN if winner == "PLAYER WINS" else RED, WIDTH//2, HEIGHT//2 - 50)
            draw_text("R: Rematch | M: Menu", 30, WHITE, WIDTH//2, HEIGHT//2 + 20)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()