import pygame
import random
import os

# --- INITIALIZATION & CONSTANTS ---
pygame.init()
WIDTH, HEIGHT = 1400, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Street Fighter Style Engine")
clock = pygame.time.Clock()
FPS = 60

# --- COLORS ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 50, 50)
BLUE = (50, 50, 200)
GREEN = (50, 200, 50)
YELLOW = (255, 255, 0)
GRAY = (50, 50, 50)
ORANGE = (255, 165, 0)

# --- PHYSICS CONSTANTS ---
GRAVITY = 0.8
FLOOR_Y = HEIGHT - 60
PLAYER_WIDTH, PLAYER_HEIGHT = 150, 300
SPEED = 10
JUMP_FORCE = -26        # Snappy jump
ATTACK_COOLDOWN = 30    # Duration of attack animation
SHOOT_DAMAGE = 25

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

def draw_health_bar(surface, x, y, health, max_health, color):
    ratio = health / max_health
    # Border (Black)
    pygame.draw.rect(surface, (0, 0, 0), (x - 2, y - 2, 304, 24), 3) 
    # Background (Dark Red)
    pygame.draw.rect(surface, (50, 0, 0), (x, y, 300, 20))
    # Health (Color)
    pygame.draw.rect(surface, color, (x, y, 300 * ratio, 20))

# --- CLASS: SPRITE ANIMATOR ---
class SpriteAnimator:
    def __init__(self, character_name, scale_factor=3.0):
        self.character_name = character_name
        self.scale = scale_factor
        self.animation_list = {} 
        self.frame_index = 0
        self.action = "Idle" 
        self.update_time = pygame.time.get_ticks()
        self.cooldown = 80 # Speed of animation
        
        # Load sprites
        actions = ["Idle", "Run", "Jump", "Punch", "Kick", "Shield", "Hurt", "Shoot"]
        for action in actions:
            temp_list = []
            for i in range(10): # Assume max 10 frames
                try:
                    path = f"assets/{character_name}/{action}/{i}.png"
                    img = pygame.image.load(path).convert_alpha()
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
        
        if fighter.is_running:
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
            
            # One-Shot Animations (Don't Loop)
            if self.frame_index >= len(current_animation):
                if self.action in ["Punch", "Kick", "Shoot", "Jump"]:
                     self.frame_index = len(current_animation) - 1
                else:
                     self.frame_index = 0 

    def draw(self, surface, fighter):
        current_animation = self.animation_list.get(self.action, self.animation_list["Idle"])
        if not current_animation: 
            # Fallback if sprite missing
            pygame.draw.rect(surface, fighter.color, fighter.rect)
            return

        image = current_animation[self.frame_index]
        
        # Flip if facing left
        if fighter.direction == -1:
            image = pygame.transform.flip(image, True, False)

        # Center Sprite over Hitbox
        sprite_rect = image.get_rect()
        sprite_rect.centerx = fighter.rect.centerx
        sprite_rect.bottom = fighter.rect.bottom 
        surface.blit(image, sprite_rect)

class Projectile:
    sprite = None 

    def __init__(self, x, y, direction, owner_color):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.direction = direction
        self.speed = 15
        self.color = owner_color
        self.active = True
        self.lifetime = 0  # <--- NEW: Track how long it has been alive

        # Attempt to load sprite
        if Projectile.sprite is None:
            try:
                img = pygame.image.load("assets/dot.png").convert_alpha()
                Projectile.sprite = pygame.transform.scale(img, (40, 40))
            except:
                Projectile.sprite = None

    def update(self):
        self.rect.x += self.speed * self.direction
        self.lifetime += 1 # <--- NEW: Count up
        
        if self.rect.right < 0 or self.rect.left > WIDTH:
            self.active = False

    def draw(self, surface):
        # Always draw the yellow circle fallback first so we can see it
        pygame.draw.circle(surface, (255, 255, 0), self.rect.center, 15) 
        
        if Projectile.sprite:
            img_rect = Projectile.sprite.get_rect()
            img_rect.center = self.rect.center
            surface.blit(Projectile.sprite, img_rect)
                   
# --- CLASS: FIGHTER ---
class Fighter:
    def __init__(self, x, y, color, is_ai=False):
        self.rect = pygame.Rect(x, y, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.color = color
        self.is_ai = is_ai
        self.is_running = False
        # Visuals
        char_name = "Villain" if is_ai else "Hero" 
        s_fac = 0.5 if char_name == "Hero" else 0.6
        self.animator = SpriteAnimator(char_name, scale_factor=s_fac)
        
        # Physics
        self.vel_y = 0
        self.direction = 1 
        self.health = 100
        
        # State
        self.is_attacking = False
        self.attack_type = None 
        self.attack_frame = 0
        self.has_hit = False 
        
        self.is_shielding = False
        self.shield_gauge = 100
        self.shield_cooldown = 0
        
        self.has_shot = False 
        self.projectile = None
        self.shoot_anim_frame = 0
        self.combo_count = 0 
        self.last_attack_time = 0

    def move(self, dx, dy):
        if dx != 0:
            self.is_running = True
        self.rect.x += dx
        self.rect.y += dy
        # Screen Bounds
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

    def attack(self, type_str):
        if self.is_attacking or self.is_shielding: return
        self.is_attacking = True
        self.has_hit = False 
        self.attack_type = type_str
        self.attack_frame = 20 # Locks character for 20 frames

        # --- COMBO LOGIC ---
        current_time = pygame.time.get_ticks()
        # If last attack was less than 800ms ago, increment combo
        if current_time - self.last_attack_time < 800:
            self.combo_count = min(self.combo_count + 1, 3) # Max 3 hits
        else:
            self.combo_count = 1 # Reset to 1

        self.last_attack_time = current_time
        
    def shoot(self):
        if not self.has_shot and not self.is_attacking and not self.is_shielding:
            self.has_shot = True
            self.shoot_anim_frame = 20
            start_x = self.rect.right if self.direction == 1 else self.rect.left
            self.projectile = Projectile(start_x, self.rect.centery -75, self.direction, self.color)
            return True
        return False

    def toggle_shield(self, active):
        if self.shield_cooldown > 0:
            self.is_shielding = False
            return
        
        if active and self.shield_gauge > 0:
            self.is_shielding = True
            self.shield_gauge -= 1.5
            if self.shield_gauge <= 0:
                self.is_shielding = False
                self.shield_cooldown = 180 
        else:
            self.is_shielding = False
            if self.shield_gauge < 100:
                self.shield_gauge += 0.5

    def update(self):
        self.apply_gravity()
        
        # Timers
        if self.shoot_anim_frame > 0: self.shoot_anim_frame -= 1
        if self.shield_cooldown > 0: self.shield_cooldown -= 1

        hitbox = None
        if self.is_attacking:
            self.attack_frame -= 1
            
            # Hitbox active during middle of animation
            if 10 < self.attack_frame < 18:
                # --- RANGE FIX ---
                # Punch: 80 (Was 40) - Hits from a comfortable distance
                # Kick: 150 (Was 60) - Long range poke
                reach = 70 if self.attack_type == "punch" else 170
                
                if self.combo_count == 3: reach += 20 # Combo bonus
                
                if self.direction == 1:
                    hb_x = self.rect.right
                else:
                    hb_x = self.rect.left - reach
                    
                hitbox = pygame.Rect(hb_x, self.rect.y + 20, reach, 50)
            
            if self.attack_frame <= 0:
                self.is_attacking = False
                self.attack_type = None

        if self.projectile:
            self.projectile.update()
            if not self.projectile.active:
                self.projectile = None
        
        if hasattr(self, 'animator'):
            self.animator.update(self)
        self.is_running = False

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
        
        # --- DEBUG: Draw Body Hitbox (Green) ---
        #pygame.draw.rect(surface, (0, 255, 0), self.rect, 2)
        char_name = "Villain" if self.is_ai else "Hero" 
        side = 20 if char_name == "Hero" else 1070
        clr = (255, 0, 0) if char_name == "Hero" else (255, 255, 255)
        draw_health_bar(surface, side, 50, self.health, 100, clr)

        # --- DEBUG: Draw Attack Hitbox (Red) ---
        # This calculates the box exactly like 'update' does so you can see it
        if self.is_attacking and 10 < self.attack_frame < 18:
            reach = 80 if self.attack_type == "punch" else 150
            if self.combo_count == 3: reach += 20
            
            if self.direction == 1:
                hb_x = self.rect.right
            else:
                hb_x = self.rect.left - reach
            
            attack_box = pygame.Rect(hb_x, self.rect.y + 20, reach, 50)
            pygame.draw.rect(surface, (255, 0, 0), attack_box, 2)
        # ---------------------------------------


        if self.projectile:
            self.projectile.draw(surface)
        
        pygame.draw.rect(surface, (0, 255, 0), self.rect, 2)
        
        # Minimal HUD above head
        pygame.draw.rect(surface, RED, (self.rect.x, self.rect.y - 20, 50, 5))
        pygame.draw.rect(surface, GREEN, (self.rect.x, self.rect.y - 20, 50 * (self.health/100), 5))
        pygame.draw.rect(surface, BLUE, (self.rect.x, self.rect.y - 10, 50 * (self.shield_gauge/100), 3))

# --- CLASS: VILLAIN BRAIN (Custom Logic + Persistence Fix) ---
class VillainBrain:
    def __init__(self, difficulty):
        self.difficulty = difficulty
        self.action_cooldown = 0
        self.state_buffer = "IDLE"
        
        # Reaction Time: How many frames before AI "notices" a change
        if difficulty == "Easy":
            self.reaction_delay = 40 
        elif difficulty == "Medium":
            self.reaction_delay = 15 
        else: # Hard
            self.reaction_delay = 0  # Instant reaction

    def decide_action(self, villain, player):
        # 1. BUSY CHECK
        if villain.is_attacking or villain.shoot_anim_frame > 0:
            return "IDLE"

        # 2. STATE ANALYSIS
        dist = abs(villain.rect.centerx - player.rect.centerx)
        gap = max(0, dist - PLAYER_WIDTH)
        
        # Directions
        face_dir = "LEFT" if player.rect.centerx < villain.rect.centerx else "RIGHT"
        run_away_dir = "RIGHT" if face_dir == "LEFT" else "LEFT"
        run_towards_dir = face_dir

        # Status
        is_player_attacking = player.is_attacking
        can_shield = (villain.shield_gauge > 5 and villain.shield_cooldown == 0)
        
        # Am I cornered? (Cannot run away)
        is_cornered = False
        if run_away_dir == "LEFT" and villain.rect.left < 100: is_cornered = True
        if run_away_dir == "RIGHT" and villain.rect.right > 1300: is_cornered = True

        # 3. REFLEX SYSTEM (Wake up if threatened!)
        # If waiting, but player attacks close by, interrupt the wait.
        if self.action_cooldown > 0:
            if self.difficulty != "Easy" and is_player_attacking and gap < 100:
                self.action_cooldown = 0
            
            # Hard mode projectile reflex
            if self.difficulty == "Hard" and player.projectile and player.projectile.active:
                 proj_dist = abs(villain.rect.centerx - player.projectile.rect.centerx)
                 if proj_dist < 200: self.action_cooldown = 0

        # 4. COOLDOWN & PERSISTENCE CHECK (CRITICAL FIX)
        # If cooldown is active, KEEP DOING what we decided last time (Buffer)
        if self.action_cooldown > 0:
            self.action_cooldown -= 1
            # Allow Movement AND Shielding to persist
            if self.state_buffer in ["LEFT", "RIGHT", "SHIELD"]: 
                return self.state_buffer
            return "IDLE" 

        # 5. DECISION LOGIC
        final_action = "IDLE"
        self.action_cooldown = self.reaction_delay 

        # =================================================================
        # --- EASY MODE ---
        # "Shields when attacked. Rarely moves away. That's it."
        # =================================================================
        if self.difficulty == "Easy":
            if is_player_attacking:
                if can_shield:
                    final_action = "SHIELD"
                    self.action_cooldown = 30 # Hold shield
                elif random.random() < 0.3: # Rare chance to move away
                    final_action = run_away_dir
                    self.action_cooldown = 20
            else:
                final_action = "IDLE"

        # =================================================================
        # --- MEDIUM MODE ---
        # "Punch/Kick in range. Random shoot. Shield extensively. 
        #  Move/Jump away if attacked & No Shield. Counter attack gaps."
        # =================================================================
        elif self.difficulty == "Medium":
            
            # A. EMERGENCY EVASION (Attacked + NO Shield)
            if is_player_attacking and gap < 80 and not can_shield:
                if random.random() < 0.5:
                    final_action = "JUMP" # Jump in place (or directional if moving)
                else:
                    final_action = run_away_dir
                self.action_cooldown = 15

            # B. DEFENSE (Attacked + Shield Available) -> "Shield Extensively"
            elif is_player_attacking and gap < 120 and can_shield:
                final_action = "SHIELD"
                self.action_cooldown = 45 # Hold it longer for "extensive" feel

            # C. OFFENSE 1: Counter Attack (Player near, NOT attacking = Gap)
            elif not is_player_attacking and gap < 80:
                if gap < 40: final_action = "PUNCH"
                else: final_action = "KICK"

            # D. OFFENSE 2: Standard Aggression
            elif gap < 40: final_action = "PUNCH"
            elif gap < 70: final_action = "KICK"
            
            # E. RANDOM SHOOT
            elif gap > 200 and not villain.has_shot and random.random() < 0.02:
                final_action = "SHOOT"

            # F. SPACING (Move away or Jump in place)
            elif gap < 60:
                if random.random() < 0.1: final_action = "JUMP"
                else: final_action = run_away_dir
                self.action_cooldown = 10

        # =================================================================
        # --- HARD MODE (Solid Defense / Aggressive Counter) ---
        # =================================================================
        elif self.difficulty == "Hard":
            
            # 1. PROJECTILE DEFENSE
            if player.projectile and player.projectile.active:
                proj_dist = abs(villain.rect.centerx - player.projectile.rect.centerx)
                if proj_dist < 200:
                    if can_shield:
                        final_action = "SHIELD"
                        self.action_cooldown = 20
                    else:
                        final_action = "JUMP"
                        self.action_cooldown = 15
                    self.state_buffer = final_action
                    return final_action

            # 2. IMMEDIATE THREAT REACTION (Strict & Glitch-Free)
            if is_player_attacking and gap < 120:
                
                # LOGIC RULE: If shield is available, USE IT. 
                # Don't "maybe" jump. Just block the attack.
                if can_shield:
                    final_action = "SHIELD"
                    self.action_cooldown = 20 # Hold the block
                
                # LOGIC RULE: Shield is broken/empty -> MUST ESCAPE.
                # No attacking allowed here. Survival only.
                else:
                    if is_cornered:
                         final_action = "JUMP"
                         self.state_buffer = run_towards_dir # Cross-up jump
                         self.action_cooldown = 20 
                    else:
                        # Mix up escape options so it's not predictable, 
                        # but ALWAYS escape.
                        if random.random() < 0.5:
                            final_action = "JUMP"
                        else:
                            final_action = run_away_dir
                        self.action_cooldown = 15
            
            # 3. OFFENSIVE PHASE (Only when NOT under pressure)
            
            # A. CLOSE RANGE (Punch Range)
            elif gap < 50:
                # 90% Aggression
                if random.random() < 0.9:
                    final_action = "PUNCH"
                else:
                    final_action = run_away_dir 
                    self.action_cooldown = 8 

            # B. MID RANGE (Kick Range)
            elif gap < 90:
                # 85% Aggression
                if random.random() < 0.85:
                    final_action = "KICK"
                else:
                    final_action = run_away_dir 
                    self.action_cooldown = 10

            # 4. NEUTRAL / APPROACH
            else:
                # Aggressive Approach (Stalking)
                # 6% Chance per frame to close in.
                if random.random() < 0.06: 
                    final_action = run_towards_dir
                    self.action_cooldown = 20 
                
                # Fireball
                elif gap > 350 and not villain.has_shot and random.random() < 0.08:
                    final_action = "SHOOT"
                
                # Maintain Spacing
                elif gap < 60:
                    final_action = run_away_dir
                    self.action_cooldown = 8
                
                # Ready
                else:
                    final_action = "IDLE"
                    self.action_cooldown = 5


        self.state_buffer = final_action
        return final_action
     
# --- MAIN GAME LOOP ---
def main():
    running = True
    in_menu = True
    game_over = False
    
    player = Fighter(200, FLOOR_Y - PLAYER_HEIGHT, BLUE)
    villain = Fighter(600, FLOOR_Y - PLAYER_HEIGHT, RED, is_ai=True)
    bg = pygame.image.load("assets/background.png").convert()
    bg = pygame.transform.scale(bg, (WIDTH, HEIGHT))

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
            
            if in_menu and event.type == pygame.KEYDOWN:
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
            
            elif game_over and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    # Reset
                    player = Fighter(200, FLOOR_Y - PLAYER_HEIGHT, BLUE)
                    villain = Fighter(600, FLOOR_Y - PLAYER_HEIGHT, RED, is_ai=True)
                    villain.direction = -1
                    game_over = False
                    winner = ""
                if event.key == pygame.K_m:
                    in_menu = True

        if in_menu:
            draw_text("STREET FIGHTER ENGINE", 60, WHITE, WIDTH//2, 100)
            draw_text("1. EASY", 30, GREEN, WIDTH//2, 250)
            draw_text("2. MEDIUM", 30, YELLOW, WIDTH//2, 300)
            draw_text("3. HARD", 30, RED, WIDTH//2, 350)
            pygame.display.flip()
            continue

        if not game_over:
            # --- INPUT ---
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]: 
                player.move(-SPEED, 0)
                player.direction = -1
            if keys[pygame.K_RIGHT]: 
                player.move(SPEED, 0)
                player.direction = 1
            if keys[pygame.K_UP]: player.jump()
            if keys[pygame.K_a]: player.attack("punch")
            if keys[pygame.K_d]: player.attack("kick")
            if keys[pygame.K_s]: player.shoot()
            player.toggle_shield(keys[pygame.K_w])

            # --- AI BRAIN ---
            action = brain.decide_action(villain, player)
            villain.toggle_shield(False) # Reset

            if action == "LEFT": 
                villain.move(-SPEED, 0)
                villain.direction = -1
            elif action == "RIGHT": 
                villain.move(SPEED, 0)
                villain.direction = 1
            elif action == "JUMP": villain.jump()
            elif action == "PUNCH": villain.attack("punch")
            elif action == "KICK": villain.attack("kick")
            elif action == "SHIELD": villain.toggle_shield(True)
            elif action == "SHOOT": villain.shoot()

            # Always face enemy
            if player.rect.centerx < villain.rect.centerx: villain.direction = -1
            else: villain.direction = 1

            # --- PHYSICS ---
            p_hitbox = player.update()
            v_hitbox = villain.update()

            # --- COLLISION RESOLUTION (FIXED) ---
            # --- COLLISION RESOLUTION (HARD STOP) ---
            if player.rect.colliderect(villain.rect):
                # 1. Vertical Check (Cross-Up Logic)
                # "it can continue after player b body ends" -> If jumping over, ignore collision
                p_bottom = player.rect.bottom
                v_bottom = villain.rect.bottom
                
                # Check if one is significantly above the other (e.g. jumping)
                player_is_above = p_bottom < villain.rect.centery + 20
                villain_is_above = v_bottom < player.rect.centery + 20

                # Only apply "Wall" physics if they are on the same level
                if not player_is_above and not villain_is_above:
                    
                    # 2. Determine Relative Position
                    if player.rect.centerx < villain.rect.centerx:
                        # CASE A: Player is on the LEFT, Villain on RIGHT
                        
                        # If Player tries to run RIGHT into Villain
                        if keys[pygame.K_RIGHT]:
                            player.rect.right = villain.rect.left # Hard Stop
                        
                        # If Villain (AI) tries to run LEFT into Player
                        elif action == "LEFT":
                            villain.rect.left = player.rect.right # Hard Stop
                            
                        # If they spawned inside each other (glitch prevention)
                        else:
                            mid = (player.rect.centerx + villain.rect.centerx) / 2
                            player.rect.right = mid
                            villain.rect.left = mid

                    else:
                        # CASE B: Player is on the RIGHT, Villain on LEFT
                        
                        # If Player tries to run LEFT into Villain (Your specific request)
                        if keys[pygame.K_LEFT]:
                            player.rect.left = villain.rect.right # Hard Stop ("Run ends here")
                            
                        # If Villain (AI) tries to run RIGHT into Player
                        elif action == "RIGHT":
                            villain.rect.right = player.rect.left # Hard Stop
                            
                        # Glitch prevention
                        else:
                            mid = (player.rect.centerx + villain.rect.centerx) / 2
                            player.rect.left = mid
                            villain.rect.right = mid

            # --- COMBAT ---
            
            # Player Hit Check
            if p_hitbox and p_hitbox.colliderect(villain.rect) and not player.has_hit:
                player.has_hit = True
                dmg = 8 if player.attack_type == "punch" else 5
                villain.take_damage(dmg)

            # Villain Hit Check
            if v_hitbox and v_hitbox.colliderect(player.rect) and not villain.has_hit:
                villain.has_hit = True
                dmg = 8 if villain.attack_type == "punch" else 5
                player.take_damage(dmg)

            # Projectiles
            if player.projectile and player.projectile.rect.colliderect(villain.rect):
                player.projectile.active = False
                villain.take_damage(SHOOT_DAMAGE)

            if villain.projectile and villain.projectile.rect.colliderect(player.rect):
                villain.projectile.active = False
                player.take_damage(SHOOT_DAMAGE)

            # Game Over
            if player.health <= 0:
                winner = "VILLAIN WINS"
                game_over = True
            elif villain.health <= 0:
                winner = "PLAYER WINS"
                game_over = True

        # --- DRAWING ---
        # Background Floor
        screen.blit(bg, (0, 0))

        
        player.draw(screen)
        villain.draw(screen)
        
        # HUD
        draw_text(f"P1: {int(player.health)}", 20, WHITE, 100, 30)
        draw_text(f"CPU: {int(villain.health)}", 20, WHITE, WIDTH-100, 30)
        
        if game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(150)
            overlay.fill(BLACK)
            screen.blit(overlay, (0,0))
            draw_text(winner, 60, GREEN if winner == "PLAYER WINS" else RED, WIDTH//2, HEIGHT//2)
            draw_text("Press R to Restart", 30, WHITE, WIDTH//2, HEIGHT//2 + 50)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()