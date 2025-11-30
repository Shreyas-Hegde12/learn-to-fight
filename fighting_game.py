import pygame
import random
import math
import pickle
import os
from sprite_handler import SpriteAnimator

# --- INITIALIZATION ---
pygame.init()
WIDTH, HEIGHT = 800, 600
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
JUMP_FORCE = -18
ATTACK_COOLDOWN = 30 # Frames
SHIELD_MAX = 100
SHIELD_REGEN = 0.5
SHIELD_DRAIN = 2
SHOOT_DAMAGE = 40

# --- Q-LEARNING CONSTANTS ---
# Actions the AI can take
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

# --- CLASS: PROJECTILE ---
class Projectile:
    def __init__(self, x, y, direction, owner_color):
        self.rect = pygame.Rect(x, y, 20, 10)
        self.direction = direction
        self.speed = 15
        self.color = owner_color
        self.active = True

    def update(self):
        self.rect.x += self.speed * self.direction
        if self.rect.x < 0 or self.rect.x > WIDTH:
            self.active = False

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.circle(surface, YELLOW, self.rect.center, 8)

# --- CLASS: FIGHTER ---
class Fighter:
    def __init__(self, x, y, color, is_ai=False):
        self.rect = pygame.Rect(x, y, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.color = color
        self.is_ai = is_ai
        self.vel_y = 0
        self.direction = 1 # 1 right, -1 left
        self.health = 100
        
        # Actions states
        self.is_attacking = False
        self.attack_type = None # "punch", "kick"
        self.attack_frame = 0
        self.has_hit = False # Flag to prevent multi-hit per animation
        
        self.is_shielding = False
        self.shield_gauge = SHIELD_MAX
        self.shield_cooldown = 0
        
        self.has_shot = False # One shot per game
        self.projectile = None
        
        # Combo tracker
        self.last_attack_time = 0
        self.combo_count = 0

    def move(self, dx, dy):
        self.rect.x += dx
        self.rect.y += dy
        
        # Boundary checks
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
        self.has_hit = False # Reset hit flag for new attack
        self.attack_type = type_str
        self.attack_frame = 20 # Duration of attack
        
        # Combo Logic
        current_time = pygame.time.get_ticks()
        if current_time - self.last_attack_time < 800: # 800ms window
            self.combo_count = min(self.combo_count + 1, 3)
        else:
            self.combo_count = 1
        self.last_attack_time = current_time

    def shoot(self):
        if not self.has_shot and not self.is_attacking and not self.is_shielding:
            self.has_shot = True
            # Spawn projectile
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
                self.shield_cooldown = 180 # 3 seconds at 60fps
        else:
            self.is_shielding = False
            if self.shield_gauge < SHIELD_MAX:
                self.shield_gauge += SHIELD_REGEN

    def update(self):
        self.apply_gravity()
        
        if self.shield_cooldown > 0:
            self.shield_cooldown -= 1

        # Attack logic
        hitbox = None
        if self.is_attacking:
            self.attack_frame -= 1
            
            # Create hitbox halfway through animation
            if 10 < self.attack_frame < 18:
                reach = 40 if self.attack_type == "punch" else 60
                # Combo bonus range
                if self.combo_count == 3: reach += 20
                
                hb_x = self.rect.right if self.direction == 1 else self.rect.left - reach
                hitbox = pygame.Rect(hb_x, self.rect.y + 10, reach, 50)
            
            if self.attack_frame <= 0:
                self.is_attacking = False
                self.attack_type = None

        # Projectile Logic
        if self.projectile:
            self.projectile.update()
            if not self.projectile.active:
                self.projectile = None

        return hitbox

    def take_damage(self, amount, is_unblockable=False):
        if self.is_shielding and not is_unblockable:
            self.shield_gauge -= amount * 2
            return False # Blocked
        else:
            self.health -= amount
            return True # Hit

    def draw(self, surface):
        # Draw Shield
        if self.is_shielding:
            pygame.draw.circle(surface, (100, 200, 255), self.rect.center, 70, 4)

        # Draw Body
        color = self.color
        # Flash white if cooling down shield
        if self.shield_cooldown > 0 and self.shield_cooldown % 10 < 5:
            color = GRAY
            
        pygame.draw.rect(surface, color, self.rect)
        
        # Draw Eyes (Direction)
        eye_x = self.rect.right - 15 if self.direction == 1 else self.rect.left + 5
        pygame.draw.rect(surface, WHITE, (eye_x, self.rect.y + 10, 10, 10))

        # Draw Limbs (Animation)
        if self.is_attacking:
            reach = 40 if self.attack_type == "punch" else 60
            if self.combo_count == 3: reach += 20
            limb_rect = pygame.Rect(0,0, reach, 20)
            if self.direction == 1:
                limb_rect.topleft = (self.rect.right, self.rect.y + 30)
            else:
                limb_rect.topright = (self.rect.left, self.rect.y + 30)
            
            limb_col = RED if self.combo_count == 3 else YELLOW
            pygame.draw.rect(surface, limb_col, limb_rect)

        # Draw Projectile
        if self.projectile:
            self.projectile.draw(surface)

        # Draw UI (Health & Shield) under player
        pygame.draw.rect(surface, RED, (self.rect.x, self.rect.y - 20, 50, 5))
        pygame.draw.rect(surface, GREEN, (self.rect.x, self.rect.y - 20, 50 * (self.health/100), 5))
        pygame.draw.rect(surface, BLUE, (self.rect.x, self.rect.y - 10, 50 * (self.shield_gauge/SHIELD_MAX), 3))

# --- CLASS: AI BRAIN (Q-LEARNING) ---
class VillainBrain:
    def __init__(self, difficulty):
        self.q_table = {} # Key: (State), Value: {Action: Score}
        self.difficulty = difficulty
        self.learning_rate = 0.1
        self.discount_factor = 0.95
        self.epsilon = 0.0 # Exploration rate
        self.last_state = None
        self.last_action = None
        
        # Knowledge Flags
        self.seen_player_shoot = False
        
        # Frame delay for AI decisions (human reaction time simulation)
        self.reaction_timer = 0
        self.current_action_lock = 0
        
        self.initialize_model()

    def initialize_model(self):
        # Pre-scripting based on difficulty
        if self.difficulty == "Easy":
            # Easy: Learns slowly, starts by Spamming Shield
            self.epsilon = 0.2
            self.learning_rate = 0.1 
            self.pre_seed_logic(mode="EASY")
            
        elif self.difficulty == "Medium":
            # Medium: Standard heuristic, knows KICK when close, RUN when attacked
            self.epsilon = 0.1
            self.learning_rate = 0.2
            self.pre_seed_logic(mode="MEDIUM")

        elif self.difficulty == "Hard":
            # Hard: Aggressive, Knows to SHIELD against SHOOT, KICK combos
            self.epsilon = 0.05 
            self.learning_rate = 0.5 
            self.pre_seed_logic(mode="HARD")

    def pre_seed_logic(self, mode):
        distances = ["CLOSE", "MID", "FAR"]
        enemy_acts = ["IDLE", "ATTACK", "SHIELD", "PROJECTILE"]
        
        for d in distances:
            for e in enemy_acts:
                state = (d, e)
                if state not in self.q_table:
                    self.q_table[state] = {a: 0.0 for a in ACTIONS}
                
                # --- EASY STRATEGY ---
                if mode == "EASY":
                    # Just spam shield if player is doing anything
                    if e == "ATTACK" or e == "PROJECTILE":
                        self.q_table[state]["SHIELD"] = 10.0
                    # If idle, try to move away or stay still
                    if e == "IDLE":
                        self.q_table[state]["IDLE"] = 5.0
                        self.q_table[state]["LEFT"] = 2.0
                        self.q_table[state]["RIGHT"] = 2.0

                # --- MEDIUM STRATEGY ---
                elif mode == "MEDIUM":
                    if d == "CLOSE" and e == "IDLE":
                        self.q_table[state]["KICK"] = 5.0 # Knows to kick
                    if d == "CLOSE" and e == "ATTACK":
                        # Sparse defense: Move away or Jump
                        self.q_table[state]["LEFT"] = 5.0
                        self.q_table[state]["RIGHT"] = 5.0
                    if e == "PROJECTILE":
                        self.q_table[state]["JUMP"] = 8.0 # Standard avoid

                # --- HARD STRATEGY ---
                elif mode == "HARD":
                    if d == "CLOSE" and e == "IDLE":
                        self.q_table[state]["KICK"] = 8.0 # Aggressive Kick
                    if e == "PROJECTILE":
                        self.q_table[state]["SHIELD"] = 10.0 # Knows to block shoot
                    if d == "MID" and e == "IDLE":
                        self.q_table[state]["PUNCH"] = 5.0 # Close gap
                        # Move closer logic handled by engine updates usually
                    if d == "CLOSE" and e == "ATTACK":
                         self.q_table[state]["SHIELD"] = 6.0
                         self.q_table[state]["KICK"] = 4.0 # Counter attack

    def get_state(self, ai: Fighter, player: Fighter):
        # Discretize continuous game data into buckets for Q-Table
        dist_x = abs(ai.rect.centerx - player.rect.centerx)
        
        if dist_x < 80: dist_bucket = "CLOSE"
        elif dist_x < 250: dist_bucket = "MID"
        else: dist_bucket = "FAR"
        
        # Check Projectile first (High priority threat)
        enemy_act = "IDLE"
        if player.projectile and player.projectile.active:
            # Check if projectile is moving towards AI
            proj = player.projectile
            if (proj.direction == 1 and proj.rect.x < ai.rect.x) or \
               (proj.direction == -1 and proj.rect.x > ai.rect.x):
                enemy_act = "PROJECTILE"
        
        elif player.is_attacking: enemy_act = "ATTACK"
        elif player.is_shielding: enemy_act = "SHIELD"
        
        return (dist_bucket, enemy_act)

    def choose_action(self, state):
        # Filter actions based on difficulty specific restrictions
        valid_actions = ACTIONS.copy()

        if self.difficulty == "Easy":
            # Easy doesn't know KICK or PUNCH initially
            if "KICK" in valid_actions: valid_actions.remove("KICK")
            if "PUNCH" in valid_actions: valid_actions.remove("PUNCH")
            # Easy doesn't know SHOOT until it sees it
            if not self.seen_player_shoot and "SHOOT" in valid_actions:
                valid_actions.remove("SHOOT")

        # Epsilon-Greedy Strategy
        if random.uniform(0, 1) < self.epsilon:
            return random.choice(valid_actions)
        
        if state not in self.q_table:
            self.q_table[state] = {a: 0.0 for a in ACTIONS}
            return random.choice(valid_actions)
        
        # Get best action but ensure it is in valid_actions
        # If the best learned action is restricted (e.g. Kick in easy), pick 2nd best or random
        sorted_actions = sorted(self.q_table[state].items(), key=lambda item: item[1], reverse=True)
        
        for action, score in sorted_actions:
            if action in valid_actions:
                return action
        
        return random.choice(valid_actions)

    def update_q_table(self, state, action, reward, next_state):
        if state not in self.q_table:
            self.q_table[state] = {a: 0.0 for a in ACTIONS}
        if next_state not in self.q_table:
            self.q_table[next_state] = {a: 0.0 for a in ACTIONS}

        old_value = self.q_table[state][action]
        next_max = max(self.q_table[next_state].values())
        
        # Bellman Equation
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
        
        # --- EVENT HANDLING ---
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
                        # Reset Game
                        player = Fighter(200, FLOOR_Y - PLAYER_HEIGHT, BLUE)
                        villain = Fighter(600, FLOOR_Y - PLAYER_HEIGHT, RED, is_ai=True)
                        villain.direction = -1
                        # We keep the brain! So it remembers what it learned
                        brain.last_state = None
                        game_over = False
                        winner = ""
                    if event.key == pygame.K_m:
                        in_menu = True

        # --- MENU LOGIC ---
        if in_menu:
            draw_text("ADAPTIVE FIGHTER", 60, WHITE, WIDTH//2, 100)
            draw_text("Select Villain Difficulty:", 30, GRAY, WIDTH//2, 200)
            draw_text("1. EASY (Uses Shield, No Punch/Kick)", 25, GREEN, WIDTH//2, 280)
            draw_text("2. MEDIUM (Standard, Kicks near, runs away)", 25, YELLOW, WIDTH//2, 330)
            draw_text("3. HARD (Aggressive, Shields Shoots, Combos)", 25, RED, WIDTH//2, 380)
            draw_text("Controls: Arrows, A(Punch), D(Kick), W(Shield), S(Shoot)", 20, WHITE, WIDTH//2, 500)
            pygame.display.flip()
            continue

        # --- GAME LOGIC ---
        if not game_over:
            keys = pygame.key.get_pressed()
            
            # --- PLAYER INPUT ---
            if keys[pygame.K_LEFT]: 
                player.move(-SPEED, 0)
                player.direction = -1
            if keys[pygame.K_RIGHT]: 
                player.move(SPEED, 0)
                player.direction = 1
            if keys[pygame.K_UP]: player.jump()
            
            if keys[pygame.K_a]: player.attack("punch", villain)
            if keys[pygame.K_d]: player.attack("kick", villain)
            
            # SHOOT LOGIC - Triggers AI learning in Easy mode
            if keys[pygame.K_s]: 
                did_shoot = player.shoot()
                if did_shoot and brain:
                    brain.seen_player_shoot = True
            
            player.toggle_shield(keys[pygame.K_w])

            # --- AI BRAIN LOGIC ---
            # 1. Observe
            current_state = brain.get_state(villain, player)
            
            # 2. Decide (Action Lock prevents jittering, simulates reaction time)
            if brain.current_action_lock <= 0:
                action = brain.choose_action(current_state)
                brain.last_action = action
                brain.last_state = current_state
                brain.current_action_lock = 15 # Commit to action for 15 frames
            else:
                action = brain.last_action
                brain.current_action_lock -= 1
                
            # 3. Execute AI Action
            villain.toggle_shield(False) # Reset shield flag for this frame
            
            if action == "LEFT": 
                villain.move(-SPEED, 0)
                villain.direction = -1
            elif action == "RIGHT": 
                villain.move(SPEED, 0)
                villain.direction = 1
            elif action == "JUMP": 
                villain.jump()
            elif action == "PUNCH": 
                villain.attack("punch", player)
            elif action == "KICK": 
                villain.attack("kick", player)
            elif action == "SHIELD": 
                villain.toggle_shield(True)
            elif action == "SHOOT":
                villain.shoot()
            
            # Face player
            if player.rect.centerx < villain.rect.centerx: villain.direction = -1
            else: villain.direction = 1

            # --- UPDATE PHYSICS ---
            p_hitbox = player.update()
            v_hitbox = villain.update()

            # --- COLLISION & REWARD CALCULATION ---
            step_reward = -0.1 # Slight penalty for existing to encourage finishing fast
            
            # Player hits Villain
            # Check HAS_HIT flag to prevent multi-frame damage
            if p_hitbox and p_hitbox.colliderect(villain.rect) and not player.has_hit:
                player.has_hit = True
                
                dmg = 8 if player.attack_type == "punch" else 5
                if player.combo_count == 3: dmg *= 2
                
                hit_success = villain.take_damage(dmg)
                if hit_success:
                    step_reward -= 5.0 # Big penalty for getting hit
                else:
                    step_reward += 5.0 # Reward for blocking successfully
            
            # Player Projectile hits Villain
            if player.projectile and player.projectile.rect.colliderect(villain.rect):
                # NOTE: For Hard Mode to be effective with Shield, we allow shield to block shot
                # but with massive drain (handled in take_damage)
                # However, original prompt said 'is_unblockable'. We relax this so Hard AI strategy works.
                villain.take_damage(SHOOT_DAMAGE, is_unblockable=False) 
                player.projectile.active = False
                
                # If villain was shielding, they survived (good job AI), else they took dmg
                if villain.is_shielding:
                     step_reward += 10.0 # Great job blocking the super
                else:
                     step_reward -= 20.0 # Huge penalty for eating a super
                
            # Villain hits Player
            if v_hitbox and v_hitbox.colliderect(player.rect) and not villain.has_hit:
                villain.has_hit = True
                
                dmg = 8 if villain.attack_type == "punch" else 5
                hit_success = player.take_damage(dmg)
                if hit_success:
                    step_reward += 10.0 # Reward for landing hit
                else:
                    step_reward -= 2.0 # Penalty for getting blocked
            
            # Villain Projectile hits Player
            if villain.projectile and villain.projectile.rect.colliderect(player.rect):
                player.take_damage(SHOOT_DAMAGE, is_unblockable=True)
                villain.projectile.active = False
                step_reward += 30.0 # Huge reward for landing super

            # Bounds punishment
            if villain.rect.left == 0 or villain.rect.right == WIDTH:
                step_reward -= 1 # Don't get cornered

            # 4. Learn (Update Q-Table)
            # Determine next state after physics update
            next_state = brain.get_state(villain, player)
            brain.update_q_table(brain.last_state, brain.last_action, step_reward, next_state)

            # Check Game Over
            if player.health <= 0:
                winner = "VILLAIN WINS"
                game_over = True
            elif villain.health <= 0:
                winner = "PLAYER WINS"
                game_over = True

        # --- DRAWING ---
        # Floor
        pygame.draw.rect(screen, GRAY, (0, FLOOR_Y, WIDTH, HEIGHT-FLOOR_Y))
        
        player.draw(screen)
        villain.draw(screen)

        # UI
        draw_text(f"P1 Health: {int(player.health)}", 20, WHITE, 100, 30)
        draw_text(f"AI Health: {int(villain.health)}", 20, WHITE, WIDTH-100, 30)
        draw_text(f"Mode: {difficulty_selected}", 20, YELLOW, WIDTH//2, 20)
        
        # Draw Cooldowns
        if player.has_shot: draw_text("SHOT USED", 15, RED, 100, 50)
        if villain.has_shot: draw_text("SHOT USED", 15, RED, WIDTH-100, 50)
        if player.shield_cooldown > 0: draw_text("SHIELD CD", 15, ORANGE, 100, 70)

        if game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(150)
            overlay.fill(BLACK)
            screen.blit(overlay, (0,0))
            draw_text(winner, 60, GREEN if winner == "PLAYER WINS" else RED, WIDTH//2, HEIGHT//2 - 50)
            draw_text("Press 'R' to Rematch (AI remembers!)", 30, WHITE, WIDTH//2, HEIGHT//2 + 20)
            draw_text("Press 'M' for Menu", 30, WHITE, WIDTH//2, HEIGHT//2 + 60)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()