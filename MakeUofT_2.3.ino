#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>


#define PIN_BCLK 4
#define PIN_LRC  5
#define PIN_DIN  6
#define PIN_BTN  2


static const int SAMPLE_RATE = 44100;
static const int16_t AMP = 11500; 
static float phase = 0.0f;

struct Note { float f; int ms; };

const Note song1[] = {
  {246.94, 250}, {0, 60}, {261.63, 250}, {0, 40}, {293.66, 250}, {0, 60}, {329.63, 250}, {0, 60},
  {329.63, 250}, {0, 60}, {392.00, 250}, {0, 60}, {392.00, 250}, {0, 40}, {392.00, 250}, {0, 60},
  {349.23, 500}, {0, 120}, {261.63, 250}, {0, 60}, {293.66, 250}, {0, 60}, {293.66, 250}, {0, 60},
  {349.23, 250}, {0, 60}, {392.00, 250}, {0, 40}, {349.23, 250}, {0, 60}, {329.63, 500}, {0, 120},
  {261.63, 250}, {0, 60}, {261.63, 250}, {0, 60}, {329.63, 250}, {0, 40}, {349.23, 250}, {0, 60},
  {329.63, 250}, {0, 60}, {293.66, 500}, {0, 90}, {220.00, 250}, {0, 30}, {220.00, 250}, {0, 30},
  {246.94, 250}, {0, 60}, {261.63, 250}, {0, 60}, {261.63, 250}, {0, 60}, {329.63, 250}, {0, 60},
  {349.23, 250}, {0, 30}, {329.63, 250}, {0, 60}, {293.66, 500}, {0, 120}
};
const int song1_len = sizeof(song1) / sizeof(song1[0]);

const Note song2[] = {
  {349.23, 250}, {0, 90}, {369.99, 250}, {0, 120}, {311.13, 250}, {0, 60}, {369.99, 250}, {0, 60},
  {415.30, 250}, {0, 60}, {277.18, 250}, {0, 60}, {349.23, 250}, {0, 60}, {369.99, 250}, {0, 120},
  {311.13, 250}, {0, 40}, {369.99, 250}, {0, 40}, {466.16, 250}, {0, 60}, {493.88, 250}, {0, 90},
  {466.16, 250}, {0, 50}, {415.30, 250}, {0, 50}, {369.99, 250}, {0, 50}, {233.08, 250}, {0, 40},
  {311.13, 250}, {0, 60}, {369.99, 250}, {0, 60}, {415.30, 250}, {0, 90}, {277.18, 250}, {0, 60},
  {349.23, 250}, {0, 60}, {369.99, 500}, {0, 120}
};
const int song2_len = sizeof(song2) / sizeof(song2[0]);

enum State { IDLE, PLAYING_1, PLAYING_2 };
State state = IDLE;

int noteIdx = 0;
unsigned long noteStartMs = 0;

const unsigned long DEBOUNCE_MS = 30;
const unsigned long DOUBLE_CLICK_WINDOW_MS = 350;

bool lastBtnRead = HIGH;
unsigned long lastChangeMs = 0;
int clickCount = 0;
unsigned long firstClickMs = 0;
bool countedThisPress = false;

void i2sInit() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 256;
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  
  i2s_pin_config_t pin = { .bck_io_num = PIN_BCLK, .ws_io_num = PIN_LRC, .data_out_num = PIN_DIN, .data_in_num = I2S_PIN_NO_CHANGE };
  i2s_set_pin(I2S_NUM_0, &pin);
}

void playChunk(float f_hz) {
  static int16_t buf[512];
  for (int i = 0; i < 256; i++) {
    int16_t v = 0;
    if (f_hz > 1.0f) {
      v = (int16_t)(sinf(phase) * AMP);
      phase += 2.0f * (float)M_PI * f_hz / (float)SAMPLE_RATE;
      if (phase > 2.0f * (float)M_PI) phase -= 2.0f * (float)M_PI;
    } else {
      phase = 0; 
    }
    buf[i*2 + 0] = v; buf[i*2 + 1] = v;
  }
  size_t written;
  i2s_write(I2S_NUM_0, buf, sizeof(buf), &written, portMAX_DELAY);
}

void checkButton(unsigned long now) {
  bool btn = digitalRead(PIN_BTN);
  if (btn != lastBtnRead) {
    lastChangeMs = now;
    lastBtnRead = btn;
  }
  if ((now - lastChangeMs) > DEBOUNCE_MS) {
    if (btn == LOW && !countedThisPress) {
      countedThisPress = true;
      if (clickCount == 0) {
        clickCount = 1;
        firstClickMs = now;
      } else if (clickCount == 1) {
        if (now - firstClickMs <= DOUBLE_CLICK_WINDOW_MS) {
          clickCount = 0;
          state = PLAYING_2; 
          noteIdx = 0;
          noteStartMs = now;
        }
      }
    }
    if (btn == HIGH) countedThisPress = false;
  }
  if (clickCount == 1 && (now - firstClickMs > DOUBLE_CLICK_WINDOW_MS)) {
    clickCount = 0;
    state = PLAYING_1; 
    noteIdx = 0;
    noteStartMs = now;
  }
}

void setup() {
  pinMode(PIN_BTN, INPUT_PULLUP);
  i2sInit();
}

void loop() {
  unsigned long now = millis();
  checkButton(now);

  if (state == PLAYING_1 || state == PLAYING_2) {
    const Note* currentSong = (state == PLAYING_1) ? song1 : song2;
    int currentLen = (state == PLAYING_1) ? song1_len : song2_len;

    if (now - noteStartMs >= (unsigned long)currentSong[noteIdx].ms) {
      noteIdx++;
      noteStartMs = now;
      
      if (noteIdx >= currentLen) {
        for(int j=0; j<10; j++) playChunk(0); 
        noteIdx = 0; 
      }
    }
    playChunk(currentSong[noteIdx].f);
  } else {
    playChunk(0);
    delay(1); // IDLE状态极小延迟节省功耗
  }
}
