SERVO HAND - TEST KIT
=====================
Print this first, before the full hand. It checks the joint fit, the pin
holes, the fishing-line channels and the servo mount on your printer.

What's in it (about 30 g of PLA, roughly 2-3 hours on the MakerBot):
  test_index_proximal / middle / distal  - the real index finger
  test_knuckle                           - the index knuckle from the palm, with a flat foot
  test_servo_mount                       - one servo mount, same as in the forearm
  test_plate_all_in_one                  - all 5 parts already laid out on one plate

MakerBot Replicator+ (MakerBot Print):
  1. Add File -> test_plate_all_in_one.stl (or add the separate STLs).
     Don't rotate anything; the parts are already the right way up.
  2. Print Settings -> Standard quality. Raft on is fine. Supports off.
  3. Material: PLA (the Replicator+ smart extruder is for PLA).
  4. Watch the first layers, then leave it.

Shorter run: print only test_knuckle + test_index_proximal (about 1 hour).

What to check:
  [ ] A 2 mm drill turns through every pin hole by hand.
  [ ] 1.75 mm filament grips in the knuckle's outer lugs and spins in the finger's middle tab.
  [ ] Linked with filament pins, the finger flops open and shut under its own weight.
  [ ] Fishing line pushes through each 2.2 mm channel from end to end.
  [ ] Your servo drops into the mount, the tabs sit on the pillars and the screws bite.

If the joints are too tight: tell Claude and the clearance can be opened up
(CLR in build.py, currently 0.4 mm per side).

Resin printer (Elegoo Mars 2 Pro): it can print the finger, but standard resin
is brittle, so the thin pin lugs tend to snap. Use the MakerBot for these parts.
