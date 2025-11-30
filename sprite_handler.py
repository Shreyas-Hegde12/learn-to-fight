class SpriteAnimator:
    def __init__(self, character_name, scale_factor=3.0):
        self.character_name = character_name
        self.scale = scale_factor
        self.animation_list = {} 
        self.frame_index = 0
        self.action = "Idle" # Current action playing
        self.update_time = pygame.time.get_ticks()
        self.cooldown = 100 # Milliseconds per frame (speed of animation)
        
        # Load all animation types automatically
        # Ensure your folder names match these keys exactly
        actions = ["Idle", "Run", "Jump", "Punch", "Kick", "Shield", "Hurt", "Shoot"]
        
        for action in actions:
            temp_list = []
            # We assume a max of 10 frames per folder to be safe, loops until file not found
            for i in range(10):
                try:
                    # Path: assets/Hero/Idle/0.png
                    img_path = f"assets/{character_name}/{action}/{i}.png"
                    img = pygame.image.load(img_path).convert_alpha()
                    
                    # Scale pixel art up
                    w = int(img.get_width() * self.scale)
                    h = int(img.get_height() * self.scale)
                    img = pygame.transform.scale(img, (w, h))
                    temp_list.append(img)
                except FileNotFoundError:
                    break # Stop loading this action when we run out of numbers
            
            self.animation_list[action] = temp_list

    def get_state(self, fighter):
        """
        Translates Fighter variable flags into an Animation Action String
        Priority: Hurt > Shield > Attack > Jump > Run > Idle
        """
        # You can add a 'is_hurt' flag to your Fighter later, for now we simulate
        # If you implemented a 'stun' or 'hurt' timer, check that first.
        
        if fighter.is_shielding:
            return "Shield"
        
        if fighter.is_attacking:
            if fighter.attack_type == "punch": return "Punch"
            if fighter.attack_type == "kick": return "Kick"
        
        # Check Jump (Vel Y is not 0)
        if fighter.vel_y != 0:
            return "Jump"
            
        # Check Shooting
        # (You might need to add a temporary flag for shooting animation duration)
        
        # Check Movement
        # We compare centers, or check keys in main loop. 
        # Better: Fighter class should know if it is "walking"
        # For now, we infer based on previous frame or input.
        keys = pygame.key.get_pressed()
        # Note: This input check is specific to Player. AI needs its own "is_moving" flag.
        if not fighter.is_ai and (keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]):
            return "Run"
        
        # Simple AI movement check (if x velocity existed, or infer from change)
        # For this logic, we default to Idle if not jumping/attacking/shielding
        return "Idle"

    def update(self, fighter):
        """Updates the frame index based on time"""
        new_action = self.get_state(fighter)

        # Check if action changed
        if new_action != self.action:
            self.action = new_action
            self.frame_index = 0
            self.update_time = pygame.time.get_ticks()

        # Handle Animation Loop
        current_animation = self.animation_list.get(self.action, self.animation_list["Idle"])
        
        # Update image if enough time passed
        if pygame.time.get_ticks() - self.update_time > self.cooldown:
            self.frame_index += 1
            self.update_time = pygame.time.get_ticks()
            
            # Loop logic
            if self.frame_index >= len(current_animation):
                # If it's an attack, we might not want to loop? 
                # For now, we loop everything, but you can add logic here to freeze on last frame.
                self.frame_index = 0 

    def draw(self, surface, fighter):
        """Draws the current frame centered on the fighter rect"""
        current_animation = self.animation_list.get(self.action, self.animation_list["Idle"])
        
        # Safety check if animation folder was empty
        if not current_animation: 
            pygame.draw.rect(surface, fighter.color, fighter.rect) # Fallback
            return

        # Get Image
        image = current_animation[self.frame_index]
        
        # Flip if facing left (direction == -1)
        if fighter.direction == -1:
            image = pygame.transform.flip(image, True, False)

        # Center Sprite over Hitbox
        # Sprite rect is likely larger than physics rect (50x100)
        sprite_rect = image.get_rect()
        sprite_rect.centerx = fighter.rect.centerx
        sprite_rect.bottom = fighter.rect.bottom # Align feet
        
        surface.blit(image, sprite_rect)