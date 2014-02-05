aws
===

Arduino based Weather Station

For an educational project for geography-minded people, I created a few programs to make an Arduino Leonaro usable as a small DYI project to create a working digital weather station. Hardware ingredients: Arduino Leonardo, RHT03 sensor, BMP180 (or BMP085).

Key features:
- data-logging or streaming mode
- adjustable measurement interval
- debug options
- managing measurement stations in a _microsds_ service
- sending data automatically to a _microsds_ service

**Disclaimer**

Although the functionality of the full package is pretty great, I need to point out that I didn't take the time to refactor the code, which is absolutely needed! The awsman code is that ugly that it really makes one's eyes water...
Of course, YMMV when using it, but it has proven to be pretty stable and functional.

Use it at your own risk.
