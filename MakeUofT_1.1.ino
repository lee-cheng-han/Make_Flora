// ===== NE555 控制 =====
const int RESET_PIN = 27;
const int BTN_PIN   = 13;

// ===== Tone Pins (low -> high) =====
const int N0 = 23; // 10k
const int N1 = 33; // 6.8k
const int N2 = 22; // 5.1k
const int N3 = 26; // 4.7k
const int N4 = 25; // 3.3k
const int N5 = 14; // 2.2k
const int N6 = 32; // 1k

int tones[] = {N0, N1, N2, N3, N4, N5, N6};
const int toneCount = 7;

void allOff(){
  for(int i=0;i<toneCount;i++)
    digitalWrite(tones[i], HIGH);
}

void play(int idx,int ms,int gap=70){
  allOff();
  digitalWrite(tones[idx], LOW);
  digitalWrite(RESET_PIN, HIGH);
  delay(ms);
  digitalWrite(RESET_PIN, LOW);
  delay(gap);
}

// ===== 小甜歌（主旋律）=====
const int sweet_notes[] = {
  3,4,5,4,
  3,2,3,4,
  5,6,5,4,
  3,2,1,

  2,3,4,5,
  4,3,2,3,
  4,5,6,5,
  4,3,2
};

const int sweet_durs[] = {
  220,220,380,220,
  220,220,220,380,
  220,220,220,380,
  220,220,500,

  220,220,220,380,
  220,220,220,380,
  220,220,220,380,
  220,220,600
};

const int sweet_len = sizeof(sweet_notes)/sizeof(sweet_notes[0]);

// ===== 温柔副歌 =====
const int soft_notes[] = {
  4,5,6,5,
  4,3,4,5,
  6,5,4,3,
  2,3,4,

  3,4,5,6,
  5,4,3,2,
  3,4,5,4,
  3,2,1
};

const int soft_durs[] = {
  240,240,420,240,
  240,240,240,420,
  240,240,240,420,
  240,240,600,

  240,240,240,420,
  240,240,240,420,
  240,240,240,420,
  240,240,650
};

const int soft_len = sizeof(soft_notes)/sizeof(soft_notes[0]);

// ===== Button Logic =====
bool lastReading = HIGH;
bool btnState = HIGH;
unsigned long lastDebounce = 0;
unsigned long firstClickTime = 0;
int clickCount = 0;

const unsigned long DEBOUNCE_MS = 35;
const unsigned long DOUBLECLICK_MS = 350;

bool isPlaying = false;

void playSong(const int* notes,const int* durs,int len){
  isPlaying = true;
  for(int i=0;i<len;i++){
    int idx = notes[i];
    if (idx < 0) idx = 0;
    if (idx >= toneCount) idx = toneCount - 1;
    play(idx, durs[i]);
  }
  digitalWrite(RESET_PIN, LOW);
  allOff();
  isPlaying = false;
}

void setup(){
  pinMode(RESET_PIN, OUTPUT);
  digitalWrite(RESET_PIN, LOW);

  for(int i=0;i<toneCount;i++){
    pinMode(tones[i], OUTPUT);
    digitalWrite(tones[i], HIGH);
  }

  pinMode(BTN_PIN, INPUT_PULLUP);

  delay(300);
}

void loop(){
  bool reading = digitalRead(BTN_PIN);

  if(reading != lastReading)
    lastDebounce = millis();

  if((millis()-lastDebounce) > DEBOUNCE_MS){
    if(reading != btnState){
      btnState = reading;

      if(btnState == LOW && !isPlaying){
        clickCount++;
        if(clickCount == 1)
          firstClickTime = millis();
      }
    }
  }

  lastReading = reading;

  if(clickCount > 0 && (millis()-firstClickTime) > DOUBLECLICK_MS){
    int c = clickCount;
    clickCount = 0;

    if(!isPlaying){
      if(c >= 2)
        playSong(soft_notes, soft_durs, soft_len);   // 双击：柔歌
      else
        playSong(sweet_notes, sweet_durs, sweet_len); // 单击：甜歌
    }
  }
}
