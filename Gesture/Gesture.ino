/*
  Servo Hand Mk1 - Gesture.ino (Arduino Uno)
  5 tendon-driven fingers, one servo each.

  Wiring (signal wires):
    Thumb  -> D3     Index -> D5     Middle -> D6
    Ring   -> D9     Pinky -> D10
  Servo power (red/brown) comes from a separate 5-6 V supply (3 A or more).
  Join that supply's GND to the Uno GND. Do not power 5 servos from the Uno 5V pin.

  Serial at 9600 baud, one command per line (line ending "Newline").

  1) Five finger values, 1 = finger up (straight), 0 = finger down (curled):
       pinky ring middle index thumb
       0 0 0 0 1   -> thumbs up
       0 0 0 1 0   -> point
       0 0 1 1 0   -> peace
       1 1 1 1 1   -> open hand
       0 0 0 0 0   -> fist
     Spaces or commas both work ("0,0,0,0,1").
     Change INPUT_ORDER below if you want the values in a different order.

  2) One gesture number (what Arduino_Link.py sends now):
       0 fist  1 open  2 point  3 thumbs up  4 peace
       5 OK    6 rock  7 three  8 four

  3) Words, handy for testing in the Serial Monitor:
       open | fist | point | peace | rock | thumbsup | ok | three | four | count | demo
       thumb 40   (finger name + 0..100 percent closed)
       all 50     (every finger to 50 %)
       angles     (print the current servo angles)
*/
#include <Servo.h>

const uint8_t N = 5;
enum { THUMB, INDEX, MIDDLE, RING, PINKY };
const char *NAMES[N] = {"thumb", "index", "middle", "ring", "pinky"};
const uint8_t PINS[N] = {3, 5, 6, 9, 10};

// Order of the five 0/1 values in a line. Thumb is last, so "0 0 0 0 1" = thumbs up.
const uint8_t INPUT_ORDER[N] = {PINKY, RING, MIDDLE, INDEX, THUMB};

// ---- calibrate these per finger -------------------------------------------
// OPEN_DEG  = servo angle where the finger is straight
// CLOSE_DEG = servo angle where the finger is fully curled
// If a finger moves the wrong way, swap its two numbers.
int OPEN_DEG[N]  = {10, 10, 10, 10, 10};
int CLOSE_DEG[N] = {150, 170, 170, 170, 170};
// ---------------------------------------------------------------------------

// How far the thumb curls when it is "down" (percent closed).
// With other fingers curled it stops at 30 % so it folds over them instead of jamming.
// With all four fingers up it can tuck further across the palm.
const int THUMB_DOWN_OVER_FINGERS = 30;
const int THUMB_DOWN_TUCKED = 65;

const uint8_t STEP_MS = 12;     // lower = faster motion
Servo servo[N];
float pos[N];                   // current percent closed
int target[N];                  // target percent closed

int pctToDeg(uint8_t i, float pct) {
  return OPEN_DEG[i] + (int)((CLOSE_DEG[i] - OPEN_DEG[i]) * pct / 100.0f + 0.5f);
}

void writeAll() {
  for (uint8_t i = 0; i < N; i++) servo[i].write(pctToDeg(i, pos[i]));
}

bool moving() {
  for (uint8_t i = 0; i < N; i++) if (abs(pos[i] - target[i]) > 0.5f) return true;
  return false;
}

void stepToward() {
  for (uint8_t i = 0; i < N; i++) {
    float d = target[i] - pos[i];
    if (fabs(d) <= 1.5f) pos[i] = target[i];
    else pos[i] += (d > 0 ? 1.5f : -1.5f);
  }
  writeAll();
}

void waitMove() {
  while (moving()) { stepToward(); delay(STEP_MS); }
}

void setTargets(int t, int i, int m, int r, int p) {
  target[THUMB] = t; target[INDEX] = i; target[MIDDLE] = m; target[RING] = r; target[PINKY] = p;
}

// Fingers move first and the thumb last when it closes (thumb first when it opens),
// so the thumb folds over the fingers instead of under them.
void pose(int t, int i, int m, int r, int p) {
  if (t > pos[THUMB]) {
    setTargets((int)pos[THUMB], i, m, r, p); waitMove();
    target[THUMB] = t; waitMove();
  } else {
    target[THUMB] = t; waitMove();
    setTargets(t, i, m, r, p); waitMove();
  }
}

// up[] uses the THUMB..PINKY enum order, true = finger up
void poseFromStates(const bool up[N]) {
  bool anyCurled = !up[INDEX] || !up[MIDDLE] || !up[RING] || !up[PINKY];
  int thumbDown = anyCurled ? THUMB_DOWN_OVER_FINGERS : THUMB_DOWN_TUCKED;
  pose(up[THUMB] ? 0 : thumbDown,
       up[INDEX] ? 0 : 100,
       up[MIDDLE] ? 0 : 100,
       up[RING] ? 0 : 100,
       up[PINKY] ? 0 : 100);
}

// Gesture numbers from Arduino_Link.py
bool gestureNumber(int g) {
  switch (g) {
    case 0: pose(30, 100, 100, 100, 100); return true;  // FIST
    case 1: pose(0, 0, 0, 0, 0);          return true;  // OPEN_HAND
    case 2: pose(30, 0, 100, 100, 100);   return true;  // POINT
    case 3: pose(0, 100, 100, 100, 100);  return true;  // THUMBS_UP
    case 4: pose(30, 0, 0, 100, 100);     return true;  // PEACE
    case 5: pose(65, 65, 0, 0, 0);        return true;  // OK (thumb and index meet)
    case 6: pose(0, 0, 100, 100, 0);      return true;  // ROCK_N_ROLL (thumb, index, pinky up)
    case 7: pose(30, 0, 0, 0, 100);       return true;  // THREE
    case 8: pose(65, 0, 0, 0, 0);         return true;  // FOUR (thumb tucked)
  }
  return false;
}

void countToFive() {
  pose(30, 100, 100, 100, 100); delay(400);
  pose(30, 0, 100, 100, 100);   delay(500);
  pose(30, 0, 0, 100, 100);     delay(500);
  pose(30, 0, 0, 0, 100);       delay(500);
  pose(65, 0, 0, 0, 0);         delay(500);
  pose(0, 0, 0, 0, 0);          delay(500);
}

void demo() {
  for (int g = 0; g <= 8; g++) { gestureNumber(g); delay(800); }
  countToFive();
  pose(0, 0, 0, 0, 0);
}

void printAngles() {
  for (uint8_t i = 0; i < N; i++) {
    Serial.print(NAMES[i]); Serial.print(": "); Serial.print((int)pos[i]);
    Serial.print("%  ("); Serial.print(pctToDeg(i, pos[i])); Serial.println(" deg)");
  }
}

bool isNumber(const String &s) {
  if (s.length() == 0) return false;
  for (unsigned int i = 0; i < s.length(); i++) if (!isDigit(s[i])) return false;
  return true;
}

// Splits a line on spaces into up to 6 tokens. Returns the token count.
int splitTokens(const String &line, String tok[], int maxTok) {
  int count = 0, i = 0, len = line.length();
  while (i < len && count < maxTok) {
    while (i < len && line[i] == ' ') i++;
    if (i >= len) break;
    int start = i;
    while (i < len && line[i] != ' ') i++;
    tok[count++] = line.substring(start, i);
  }
  while (i < len && line[i] == ' ') i++;
  return (i < len) ? maxTok + 1 : count;   // maxTok+1 means "too many"
}

void handle(String cmd) {
  cmd.trim(); cmd.toLowerCase();
  cmd.replace(',', ' ');
  cmd.replace('\t', ' ');
  if (cmd.length() == 0) return;

  String tok[6];
  int n = splitTokens(cmd, tok, 6);

  // 1) five 0/1 finger values
  if (n == N) {
    bool allNum = true;
    for (uint8_t k = 0; k < N; k++) if (!isNumber(tok[k])) allNum = false;
    if (allNum) {
      bool up[N];
      for (uint8_t k = 0; k < N; k++) up[INPUT_ORDER[k]] = tok[k].toInt() > 0;
      poseFromStates(up);
      Serial.print("ok: "); Serial.println(cmd);
      return;
    }
  }

  // 2) single gesture number
  if (n == 1 && isNumber(tok[0])) {
    if (gestureNumber(tok[0].toInt())) { Serial.print("ok: "); Serial.println(cmd); }
    else { Serial.print("Unknown gesture: "); Serial.println(cmd); }
    return;
  }

  // 3) words
  String key = tok[0];
  int val = (n >= 2 && isNumber(tok[1])) ? constrain((int)tok[1].toInt(), 0, 100) : -1;

  if (key == "open")          gestureNumber(1);
  else if (key == "fist")     gestureNumber(0);
  else if (key == "point")    gestureNumber(2);
  else if (key == "thumbsup") gestureNumber(3);
  else if (key == "peace")    gestureNumber(4);
  else if (key == "ok")       gestureNumber(5);
  else if (key == "rock")     gestureNumber(6);
  else if (key == "three")    gestureNumber(7);
  else if (key == "four")     gestureNumber(8);
  else if (key == "count")    countToFive();
  else if (key == "demo")     demo();
  else if (key == "angles")   printAngles();
  else if (key == "all" && val >= 0) { for (uint8_t i = 0; i < N; i++) target[i] = val; waitMove(); }
  else {
    bool found = false;
    for (uint8_t i = 0; i < N; i++) {
      if (key == NAMES[i] && val >= 0) { target[i] = val; waitMove(); found = true; }
    }
    if (!found) { Serial.print("Unknown: "); Serial.println(cmd); return; }
  }
  Serial.print("ok: "); Serial.println(cmd);
}

void setup() {
  Serial.begin(9600);
  for (uint8_t i = 0; i < N; i++) { pos[i] = 0; target[i] = 0; }
  for (uint8_t i = 0; i < N; i++) {     // attach one at a time to limit the start-up current spike
    servo[i].write(pctToDeg(i, 0));
    servo[i].attach(PINS[i]);
    delay(250);
  }
  Serial.println("Servo Hand ready.");
  Serial.println("Send 5 values (pinky ring middle index thumb), 1 = up, 0 = down. Example: 0 0 0 0 1 = thumbs up");
}

void loop() {
  if (Serial.available()) handle(Serial.readStringUntil('\n'));
}
