# Two-workshop simulation split into four sections (pygame)
# Sections:
# 1) Top-left: simulation info (text: time, speed, counts)
# 2) Top-right: control buttons (Start, Pause, Stop, x1, x2, x5, x10, x20)
# 3) Bottom-left: produced (blue/pink) and finished (green) rows
# 4) Bottom-right: workshops (WS1/WS2) + assigned times (prod/transfer/proc)
#
# Visual states:
# - Blue: producing in WS1 (shown inside WS1)
# - Light pink: produced but transfer not yet completed (shown near WS1 and as pink in produced row)
# - Red: processing in WS2 (shown inside WS2)
# - Green: finished (shown in finished row aligned with produced)
#
# Keyboard shortcuts: Space (pause/resume), S (reset), 1/2/3/4/5 -> x1/x2/x5/x10/x20

import pygame
import random
import time

# ---------------------------
# Config
# ---------------------------
WIDTH, HEIGHT = 1200, 800
FPS = 60

# Times (minutes)
PROD_MIN, PROD_MAX = 65, 85
SETUP_MIN, SETUP_MAX = 5, 15
TRANSFER_MIN, TRANSFER_MAX = 5, 11
PROC_MIN, PROC_MAX = 30, 45

# Colors
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
GRAY = (215, 215, 215)
BLUE = (30, 90, 255)
LIGHT_PINK = (255, 182, 193)
RED = (230, 60, 60)
GREEN = (40, 180, 80)

# UI buttons (top-right)
BTN_W, BTN_H = 90, 28
BTN_GAP = 10

# Produced/Finished rows (bottom-left)
CIRCLE_R = 10
CIRCLES_PER_ROW = 25
CIRCLE_GAP = 24

# Section layout
SECTION1_RECT = pygame.Rect(0, 0, WIDTH // 2, 120)                 # top-left (info)
SECTION2_RECT = pygame.Rect(WIDTH // 2, 0, WIDTH // 2, 120)        # top-right (buttons)
SECTION3_RECT = pygame.Rect(0, 120, WIDTH // 2, HEIGHT - 120)      # bottom-left (rows)
SECTION4_RECT = pygame.Rect(WIDTH // 2, 120, WIDTH // 2, HEIGHT - 120)  # bottom-right (workshops + assign)

# Workshops in section 4
WS1_RECT = pygame.Rect(SECTION4_RECT.x + 60, SECTION4_RECT.y + 80, 140, 100)
WS2_RECT = pygame.Rect(SECTION4_RECT.right - 220, SECTION4_RECT.y + 80, 160, 110)

# ---------------------------
# Product model
# ---------------------------
class Product:
    def __init__(self, pid, prod_time, setup_time, transfer_time, proc_time):
        self.pid = pid
        self.prod_time = prod_time
        self.setup_time = setup_time
        self.transfer_time = transfer_time
        self.proc_time = proc_time

        self.t_prod_start = None
        self.t_prod_done = None
        self.t_transfer_done = None
        self.t_proc_start = None
        self.t_proc_done = None

        # waiting_ws1 -> producing_ws1 -> produced -> in_queue_ws2 -> processing_ws2 -> finished
        self.state = "waiting_ws1"

        self.x = None
        self.y = None


# ---------------------------
# Simulation state
# ---------------------------
class Simulation:
    def __init__(self):
        self.reset()

    def reset(self):
        self.now = 0.0
        self.speed = 1.0
        self.running = False
        self.paused = True

        self.products = []
        self.queue_ws2 = []
        self.finished_ids = []

        self.ws1_busy_until = 0.0
        self.ws2_busy_until = 0.0
        self.ws2_current_id = None

        self.next_pid = 1
        self.assigned_list = []  # (pid, prod, transfer, proc)

        self._schedule_next_ws1()

    def _rand(self, lo, hi):
        return random.randint(lo, hi)

    def _schedule_next_ws1(self):
        prod = self._rand(PROD_MIN, PROD_MAX)
        setup = self._rand(SETUP_MIN, SETUP_MAX)
        transfer = self._rand(TRANSFER_MIN, TRANSFER_MAX)
        proc = self._rand(PROC_MIN, PROC_MAX)

        p = Product(self.next_pid, prod, setup, transfer, proc)
        p.t_prod_start = self.now
        p.state = "producing_ws1"
        p.x, p.y = WS1_RECT.center   
        self.products.append(p)

        self.ws1_busy_until = self.now + prod + setup
        self.assigned_list.append((p.pid, prod, transfer, proc))
        self.next_pid += 1

    def _try_start_ws2(self):
        if self.ws2_current_id is None and self.queue_ws2:
            pid = self.queue_ws2.pop(0)
            p = next(pp for pp in self.products if pp.pid == pid)
            p.t_proc_start = self.now
            p.state = "processing_ws2"
            self.ws2_current_id = pid
            self.ws2_busy_until = self.now + p.proc_time

    def update(self, dt_real_seconds):
        if not self.running or self.paused:
            return

        self.now += dt_real_seconds * self.speed

        # WS1 production and transfer to WS2 queue
        for p in self.products:
            if p.state == "producing_ws1":
                if self.now >= (p.t_prod_start + p.prod_time) and p.t_prod_done is None:
                    p.t_prod_done = p.t_prod_start + p.prod_time
                    p.state = "produced"

            if p.state == "produced" and p.t_transfer_done is None:
                p.state = "transferring"
                p.target_x, p.target_y = WS2_RECT.center
            elif p.state == "transferring":
                dx = (p.target_x - p.x) * 0.05
                dy = (p.target_y - p.y) * 0.05
                p.x += dx
                p.y += dy
                # وقتی به مقصد رسید
                if abs(p.x - p.target_x) < 2 and abs(p.y - p.target_y) < 2:
                    p.state = "in_queue_ws2"
                    self.queue_ws2.append(p.pid)



        # Schedule next product after WS1 busy time
        if self.now >= self.ws1_busy_until:
            last = self.products[-1] if self.products else None
            if (last is None) or (last.state in ("produced", "in_queue_ws2", "processing_ws2", "finished")):
                self._schedule_next_ws1()
                self.ws1_busy_until += 1e-6  # avoid multiple schedules within same frame

        # WS2 completion
        if self.ws2_current_id is not None:
            p = next(pp for pp in self.products if pp.pid == self.ws2_current_id)
            if self.now >= self.ws2_busy_until:
                p.t_proc_done = self.ws2_busy_until
                p.state = "finished"
                self.finished_ids.append(p.pid)
                self.ws2_current_id = None

        self._try_start_ws2()

# ---------------------------
# Drawing helpers
# ---------------------------
def draw_section_borders(screen):
    # Visual separators for the four sections
    pygame.draw.rect(screen, (180, 180, 180), SECTION1_RECT, 2)
    pygame.draw.rect(screen, (180, 180, 180), SECTION2_RECT, 2)
    pygame.draw.rect(screen, (180, 180, 180), SECTION3_RECT, 2)
    pygame.draw.rect(screen, (180, 180, 180), SECTION4_RECT, 2)

def draw_controls_text(screen, sim):
    # Top-left: info text
    font = pygame.font.SysFont("Segoe UI", 18)
    screen.blit(font.render("Simulation info", True, BLACK), (SECTION1_RECT.x + 14, SECTION1_RECT.y + 10))

    sfont = pygame.font.SysFont("Segoe UI", 16)
    screen.blit(sfont.render(f"Sim time (min): {int(sim.now)}", True, BLACK), (SECTION1_RECT.x + 14, SECTION1_RECT.y + 40))
    screen.blit(sfont.render(f"Speed: x{sim.speed:.0f}", True, BLACK), (SECTION1_RECT.x + 14, SECTION1_RECT.y + 60))
    screen.blit(sfont.render(f"WS1 produced: {sum(1 for p in sim.products if p.t_prod_done)}", True, BLACK), (SECTION1_RECT.x + 14, SECTION1_RECT.y + 80))
    screen.blit(sfont.render(f"WS2 finished: {len(sim.finished_ids)}", True, BLACK), (SECTION1_RECT.x + 14, SECTION1_RECT.y + 100))

def draw_controls_buttons(screen, btns):
    # Top-right: buttons
    font = pygame.font.SysFont("Segoe UI", 18)
    screen.blit(font.render("Control buttons", True, BLACK), (SECTION2_RECT.x + 14, SECTION2_RECT.y + 10))

    for rect, label in btns:
        pygame.draw.rect(screen, GRAY, rect, border_radius=6)
        pygame.draw.rect(screen, BLACK, rect, 2, border_radius=6)
        t = pygame.font.SysFont("Segoe UI", 16).render(label, True, BLACK)
        screen.blit(t, (rect.x + 10, rect.y + 8))

def draw_produced_finished(screen, sim):
    # Bottom-left: produced & finished rows
    font = pygame.font.SysFont("Segoe UI", 18)
    screen.blit(font.render("Produced & finished", True, BLACK), (SECTION3_RECT.x + 14, SECTION3_RECT.y + 12))

    produced = [p for p in sim.products if p.t_prod_done is not None]
    produced.sort(key=lambda x: x.pid)
    finished = set(sim.finished_ids)

    # Produced row origin
    prod_origin_x = SECTION3_RECT.x + 20
    prod_origin_y = SECTION3_RECT.y + 50

    # Finished row origin
    fin_origin_x = SECTION3_RECT.x + 20
    fin_origin_y = SECTION3_RECT.y + 210

    font_label = pygame.font.SysFont("Consolas", 14)

    # Produced circles (blue or pink if waiting transfer)
    for idx, p in enumerate(produced):
        row = idx // CIRCLES_PER_ROW
        col = idx % CIRCLES_PER_ROW
        x = prod_origin_x + col * CIRCLE_GAP
        y = prod_origin_y + row * CIRCLE_GAP
        if p.state == "produced" and p.t_transfer_done is None:
            pygame.draw.circle(screen, LIGHT_PINK, (x, y), CIRCLE_R)
        else:
            pygame.draw.circle(screen, BLUE, (x, y), CIRCLE_R)
        # Draw product ID inside circle
        label = font_label.render(f"P{p.pid}", True, BLACK)
        screen.blit(label, (x - 12, y - 8))

    # Finished circles aligned below
    for idx, p in enumerate(produced):
        if p.pid in finished:
            row = idx // CIRCLES_PER_ROW
            col = idx % CIRCLES_PER_ROW
            x = fin_origin_x + col * CIRCLE_GAP
            y = fin_origin_y + row * CIRCLE_GAP
            pygame.draw.circle(screen, GREEN, (x, y), CIRCLE_R)
            # Draw product ID inside circle
            label = font_label.render(f"P{p.pid}", True, BLACK)
            screen.blit(label, (x - 12, y - 8))

def draw_workshops_and_assign(screen, sim):
    # Bottom-right: workshops + assigned times
    font = pygame.font.SysFont("Segoe UI", 18)
    screen.blit(font.render("Workshops", True, BLACK), (SECTION4_RECT.x + 14, SECTION4_RECT.y + 12))

    # Workshop rectangles and labels
    pygame.draw.rect(screen, BLACK, WS1_RECT, 2)
    pygame.draw.rect(screen, BLACK, WS2_RECT, 2)
    screen.blit(font.render("Workshop 1", True, BLACK), (WS1_RECT.x, WS1_RECT.y - 22))
    screen.blit(font.render("Workshop 2", True, BLACK), (WS2_RECT.x, WS2_RECT.y - 22))

    # State markers inside workshops
    for p in sim.products:
        font_label = pygame.font.SysFont("Consolas", 14)

    if p.state == "producing_ws1":
        pygame.draw.circle(screen, BLUE, WS1_RECT.center, 14)
        label = font_label.render(f"P{p.pid}", True, BLACK)
        screen.blit(label, (WS1_RECT.centerx - 12, WS1_RECT.centery - 8))

    elif p.state == "produced":
        pygame.draw.circle(screen, LIGHT_PINK, (WS1_RECT.centerx + 40, WS1_RECT.centery), 12)
        label = font_label.render(f"P{p.pid}", True, BLACK)
        screen.blit(label, (WS1_RECT.centerx + 30, WS1_RECT.centery - 8))

    elif p.state == "transferring":
        pygame.draw.circle(screen, LIGHT_PINK, (int(p.x), int(p.y)), 12)
        label = font_label.render(f"P{p.pid}", True, BLACK)
        screen.blit(label, (int(p.x) - 12, int(p.y) - 8))

    elif p.state == "processing_ws2":
        pygame.draw.circle(screen, RED, WS2_RECT.center, 14)
        label = font_label.render(f"P{p.pid}", True, BLACK)
        screen.blit(label, (WS2_RECT.centerx - 12, WS2_RECT.centery - 8))

    # WS2-- info
    font2 = pygame.font.SysFont("Consolas", 16)
    q_count = len(sim.queue_ws2)
    current = sim.ws2_current_id if sim.ws2_current_id is not None else "-"
    screen.blit(font2.render(f"Queue awaiting WS2: {q_count}", True, BLACK), (WS2_RECT.x, WS2_RECT.bottom + 8))
    screen.blit(font2.render(f"WS2 current PID: {current}", True, BLACK), (WS2_RECT.x, WS2_RECT.bottom + 28))

    # Assigned times list
    screen.blit(font.render("Assigned times", True, BLACK), (SECTION4_RECT.x + 14, SECTION4_RECT.y + 230))
    labfont = pygame.font.SysFont("Consolas", 16)
    screen.blit(labfont.render("PID: prod / transfer / proc", True, BLACK), (SECTION4_RECT.x + 14, SECTION4_RECT.y + 254))

    x = SECTION4_RECT.x + 14
    y = SECTION4_RECT.y + 276
    max_rows = (SECTION4_RECT.bottom - y - 16) // 18
    for (pid, prod, transfer, proc) in sim.assigned_list[-max_rows:]:
        line = f"{pid}: {prod} / {transfer} / {proc}"
        screen.blit(labfont.render(line, True, BLACK), (x, y))
        y += 18

# ---------------------------
# Main
# ---------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Two-Workshop Simulation (four sections)")
    clock = pygame.time.Clock()

    sim = Simulation()

    # Build control buttons (top-right section)
    # خط اول: Start / Pause / Stop
    bx = SECTION2_RECT.x + 40
    by = SECTION2_RECT.y + 40
    btn_start = pygame.Rect(bx, by, BTN_W, BTN_H)
    btn_pause = pygame.Rect(btn_start.right + BTN_GAP, by, BTN_W, BTN_H)
    btn_stop  = pygame.Rect(btn_pause.right + BTN_GAP, by, BTN_W, BTN_H)

    # خط دوم: سرعت‌ها
    by2 = by + BTN_H + 12   # کمی پایین‌تر از خط اول
    btn_1x  = pygame.Rect(bx, by2, BTN_W, BTN_H)
    btn_2x  = pygame.Rect(btn_1x.right + BTN_GAP, by2, BTN_W, BTN_H)
    btn_5x  = pygame.Rect(btn_2x.right + BTN_GAP, by2, BTN_W, BTN_H)
    btn_10x = pygame.Rect(btn_5x.right + BTN_GAP, by2, BTN_W, BTN_H)
    btn_20x = pygame.Rect(btn_10x.right + BTN_GAP, by2, BTN_W, BTN_H)

    # bx = SECTION2_RECT.x + 14
    # by = SECTION2_RECT.y + 44
    # btn_start = pygame.Rect(bx, by, BTN_W, BTN_H)
    # btn_pause = pygame.Rect(btn_start.right + BTN_GAP, by, BTN_W, BTN_H)
    # btn_stop  = pygame.Rect(btn_pause.right + BTN_GAP, by, BTN_W, BTN_H)
    # btn_1x    = pygame.Rect(btn_stop.right + BTN_GAP, by, BTN_W, BTN_H)
    # btn_2x    = pygame.Rect(btn_1x.right + BTN_GAP, by, BTN_W, BTN_H)
    # btn_5x    = pygame.Rect(btn_2x.right + BTN_GAP, by, BTN_W, BTN_H)
    # btn_10x   = pygame.Rect(btn_5x.right + BTN_GAP, by, BTN_W, BTN_H)
    # btn_20x   = pygame.Rect(btn_10x.right + BTN_GAP, by, BTN_W, BTN_H)

    btns = [
        (btn_start, "Start"), (btn_pause, "Pause"), (btn_stop, "Stop"),
        (btn_1x, "x1"), (btn_2x, "x2"), (btn_5x, "x5"),
        (btn_10x, "x10"), (btn_20x, "x20")
    ]

    running = True
    last_real = time.time()

    while running:
        real_now = time.time()
        dt_real = real_now - last_real
        last_real = real_now

        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if btn_start.collidepoint(mx, my):
                    sim.running = True
                    sim.paused = False
                elif btn_pause.collidepoint(mx, my):
                    sim.paused = True
                elif btn_stop.collidepoint(mx, my):
                    sim.reset()
                elif btn_1x.collidepoint(mx, my):
                    sim.speed = 1.0
                elif btn_2x.collidepoint(mx, my):
                    sim.speed = 2.0
                elif btn_5x.collidepoint(mx, my):
                    sim.speed = 5.0
                elif btn_10x.collidepoint(mx, my):
                    sim.speed = 10.0
                elif btn_20x.collidepoint(mx, my):
                    sim.speed = 20.0

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    sim.running = True
                    sim.paused = not sim.paused
                elif event.key == pygame.K_s:
                    sim.reset()
                elif event.key == pygame.K_1:
                    sim.speed = 1.0
                elif event.key == pygame.K_2:
                    sim.speed = 2.0
                elif event.key == pygame.K_3:
                    sim.speed = 5.0
                elif event.key == pygame.K_4:
                    sim.speed = 10.0
                elif event.key == pygame.K_5:
                    sim.speed = 20.0

        # Update simulation
        sim.update(dt_real)

        # Draw
        screen.fill(WHITE)
        draw_section_borders(screen)

        # Section 1: info text (top-left)
        draw_controls_text(screen, sim)

        # Section 2: control buttons (top-right)
        draw_controls_buttons(screen, btns)

        # Section 3: produced & finished rows (bottom-left)
        draw_produced_finished(screen, sim)

        # Section 4: workshops + assigned times (bottom-right)
        draw_workshops_and_assign(screen, sim)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()