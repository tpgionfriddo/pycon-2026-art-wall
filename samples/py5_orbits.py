"""Orbiting particles with trails — live py5 sketch."""
import py5

N = 220

def setup():
    py5.size(512, 512)
    py5.color_mode(py5.HSB, 360, 100, 100, 100)
    py5.background(0)
    py5.no_stroke()

def draw():
    py5.fill(0, 0, 0, 6)                      # fading trails
    py5.rect(0, 0, py5.width, py5.height)

    t = py5.frame_count / 60
    for i in range(N):
        ang = i * py5.TWO_PI / N + t * (0.2 + (i % 7) * 0.05)
        r = 120 + 90 * py5.sin(t + i * 0.13)
        x = py5.width / 2 + r * py5.cos(ang)
        y = py5.height / 2 + r * py5.sin(ang)
        py5.fill((i * 3 + py5.frame_count) % 360, 80, 100, 60)
        py5.circle(x, y, 6)

    # py5.save_frame("frames/art-####.png")    # enable to export for the wall

py5.run_sketch()
