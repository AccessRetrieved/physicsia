import pygame
import math
import sys

# ============================================
GRAVITY = 9.81          # m/s^2
BALL_MASS = 0.00019       # kg
AIR_DENSITY = 1.2       # kg/m^3
BALL_RADIUS = 0.008      # m
DRAG_COEFF = 0.47       # sphere
WIND_SPEED = 6.0        # m/s
DROP_HEIGHT = 1.02       # m
FAN_OUTLET_HEIGHT = 0.98 # m
TIME_STEP = 0.002       # s
BALL_X_OFFSET = 0.03    # m
FAN_OUTLET_DIAMETER = 0.06  # m
# ============================================

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 600
GROUND_OFFSET_PIX = 60

pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Ball Drop in Crossflow")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 18)

max_height = max(DROP_HEIGHT, FAN_OUTLET_HEIGHT) + 0.1
usable_height_pix = WINDOW_HEIGHT - 2 * GROUND_OFFSET_PIX
SCALE = usable_height_pix / max_height

ground_y_pix = WINDOW_HEIGHT - GROUND_OFFSET_PIX
fan_x_pix = WINDOW_WIDTH // 3

BALL_COLOR = (230, 80, 80)
FAN_COLOR = (100, 100, 255)
BG_COLOR = (30, 30, 40)
GROUND_COLOR = (180, 180, 180)

ball_area = math.pi * BALL_RADIUS * BALL_RADIUS

def reset_state():
    x = BALL_X_OFFSET
    y = DROP_HEIGHT
    vx = 0.0
    vy = 0.0
    return {"x": x, "y": y, "vx": vx, "vy": vy, "t": 0.0, "landed": False, "landing_x": None}

state = reset_state()
running_sim = False

def world_to_screen(x, y):
    px = fan_x_pix + x * SCALE
    py = ground_y_pix - y * SCALE
    return int(px), int(py)

def step_state(state, dt):
    if state["landed"]:
        return state
    x = state["x"]
    y = state["y"]
    vx = state["vx"]
    vy = state["vy"]

    air_vx = WIND_SPEED
    air_vy = 0.0

    vrel_x = air_vx - vx
    vrel_y = air_vy - vy
    vrel_mag = math.hypot(vrel_x, vrel_y)

    if vrel_mag > 1e-6:
        drag_mag = 0.5 * AIR_DENSITY * DRAG_COEFF * ball_area * vrel_mag * vrel_mag
        ax_drag = drag_mag * (vrel_x / vrel_mag) / BALL_MASS
        ay_drag = drag_mag * (vrel_y / vrel_mag) / BALL_MASS
    else:
        ax_drag = 0.0
        ay_drag = 0.0

    ax = ax_drag
    ay = ay_drag - GRAVITY

    vx += ax * dt
    vy += ay * dt

    x += vx * dt
    y += vy * dt

    t = state["t"] + dt

    if y <= 0.0 and not state["landed"]:
        y = 0.0
        state["landed"] = True
        state["landing_x"] = x

    state["x"] = x
    state["y"] = y
    state["vx"] = vx
    state["vy"] = vy
    state["t"] = t
    return state

def draw_scene(state):
    screen.fill(BG_COLOR)
    pygame.draw.line(screen, GROUND_COLOR, (0, ground_y_pix), (WINDOW_WIDTH, ground_y_pix), 2)

    fan_width_pix = 40
    fan_height_pix = 60

    fan_center_y_pix = ground_y_pix - FAN_OUTLET_HEIGHT * SCALE
    fan_rect = pygame.Rect(0, 0, fan_width_pix, fan_height_pix)
    fan_rect.center = (fan_x_pix, fan_center_y_pix)
    pygame.draw.rect(screen, FAN_COLOR, fan_rect, 2)

    outlet_radius_pix = int(0.5 * FAN_OUTLET_DIAMETER * SCALE)
    pygame.draw.circle(screen, FAN_COLOR, (fan_x_pix, fan_center_y_pix), outlet_radius_pix)

    bx, by = world_to_screen(state["x"], state["y"])
    pygame.draw.circle(screen, BALL_COLOR, (bx, by), int(BALL_RADIUS * SCALE))

    text1 = font.render(f"t = {state['t']:.3f} s", True, (230, 230, 230))
    screen.blit(text1, (20, 20))
    text2 = font.render(f"x displacement = {state['x']:.3f} m", True, (230, 230, 230))
    screen.blit(text2, (20, 40))
    text3 = font.render(f"Wind speed = {WIND_SPEED:.2f} m/s", True, (230, 230, 230))
    screen.blit(text3, (20, 60))

    if state["landed"] and state["landing_x"] is not None:
        text4 = font.render(f"Landing x = {state['landing_x']:.3f} m (SPACE redo, R reset, Q quit)", True, (240, 220, 120))
        screen.blit(text4, (20, 560))
    else:
        text4 = font.render("Press SPACE to start/pause, R reset, Q quit", True, (200, 200, 200))
        screen.blit(text4, (625, 20))

    pygame.display.flip()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                pygame.quit()
                sys.exit()
            if event.key == pygame.K_SPACE:
                if state["landed"]:
                    state = reset_state()
                running_sim = not running_sim
            if event.key == pygame.K_r:
                state = reset_state()
                running_sim = False

    if running_sim and not state["landed"]:
        state = step_state(state, TIME_STEP)

    draw_scene(state)
    clock.tick(1.0 / TIME_STEP if running_sim else 60)