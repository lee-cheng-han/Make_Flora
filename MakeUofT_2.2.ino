#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

// ====== 引脚（按你接线）======
#define PIN_BCLK 4
#define PIN_LRC  5
#define PIN_DIN  6
#define PIN_BTN  2

// ====== 音频参数 ======
static const int SAMPLE_RATE = 44100;
static const int16_t AMP = 11500; // 音量
static float phase = 0.0f;

struct Note { float f; int ms; };

// ====== 1号歌：温柔慢一点（爱情氛围）=====
const Note song1[] = {
// 第一句：Oh~ baby 情话多说一点
{261.63, 250}, {0, 60}, // 1
{261.63, 250}, {0, 40}, // 1
{293.66, 250}, {0, 60}, // 2
{329.63, 250}, {0, 60}, // 3
{329.63, 250}, {0, 60}, // 3
{392.00, 250}, {0, 60}, // 5
{392.00, 250}, {0, 40}, // 5
{392.00, 250}, {0, 60}, // 5
{349.23, 500}, {0, 120},// 4 (结尾稍长)

// 第二句：想我就多看一眼
{261.63, 250}, {0, 60}, // 1
{293.66, 250}, {0, 60}, // 2
{293.66, 250}, {0, 60}, // 2
{349.23, 250}, {0, 60}, // 4
{392.00, 250}, {0, 40}, // 5
{349.23, 250}, {0, 60}, // 4
{329.63, 500}, {0, 120},// 3

// 第三句：表现多一点点
{261.63, 250}, {0, 60}, // 1
{261.63, 250}, {0, 60}, // 1
{329.63, 250}, {0, 40}, // 3
{349.23, 250}, {0, 60}, // 4
{329.63, 250}, {0, 60}, // 3
{293.66, 500}, {0, 90},// 2

// 第四句：让我能 真的看见
{220.00, 250}, {0, 30}, // 6. (低音6)
{220.00, 250}, {0, 30}, // 6. (低音6)
{246.94, 250}, {0, 60}, // 7. (低音7)
{261.63, 250}, {0, 60}, // 1
{261.63, 250}, {0, 60}, // 1
{329.63, 250}, {0, 60}, // 3
{349.23, 250}, {0, 30}, // 4
{329.63, 250}, {0, 60}, // 3
{293.66, 500}, {0, 120} // 2

};
const int song1_len = sizeof(song1) / sizeof(song1[0]);

// ====== 2号歌：明显更快更甜（心跳感）=====
const Note song2[] = {
  // 更快节奏 + 更高音区
  {659.25, 180}, {0, 40},  // E
  {739.99, 180}, {0, 40},  // F#
  {830.61, 240}, {0, 60},  // G#
  {739.99, 160}, {0, 40},  // F#
  {659.25, 160}, {0, 40},  // E
  {587.33, 260}, {0, 120}, // D（落）
  // “心跳两下”
  {659.25, 140}, {0, 60},
  {659.25, 140}, {0, 180},
  // 再甜一点收尾
  {739.99, 220}, {0, 60},
  {659.25, 520}, {0, 220}
};
const int song2_len = sizeof(song2) / sizeof(song2[0]);

enum State { IDLE, PLAYING_1, PLAYING_2 };
State state = IDLE;

int noteIdx = 0;
unsigned long noteStartMs = 0;

// ====== 双击检测参数 ======
const unsigned long DEBOUNCE_MS = 30;
const unsigned long DOUBLE_CLICK_WINDOW_MS = 320;

bool lastBtnRead = HIGH;
unsigned long lastChangeMs = 0;

// click 计数只在 IDLE 时用
int clickCount = 0;
unsigned long firstClickMs = 0;

// ====== I2S 初始化 ======
void i2sInit() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = 0;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;

  i2s_pin_config_t pin = {};
  pin.bck_io_num = PIN_BCLK;
  pin.ws_io_num = PIN_LRC;
  pin.data_out_num = PIN_DIN;
  pin.data_in_num = I2S_PIN_NO_CHANGE;

  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin);
}

void playChunk(float f_hz) {
  static int16_t buf[512]; // 256 frames * 2ch
  for (int i = 0; i < 256; i++) {
    int16_t v = 0;
    if (f_hz > 1.0f) {
      v = (int16_t)(sinf(phase) * AMP);
      phase += 2.0f * (float)M_PI * f_hz / (float)SAMPLE_RATE;
      if (phase > 2.0f * (float)M_PI) phase -= 2.0f * (float)M_PI;
    }
    buf[i*2 + 0] = v;
    buf[i*2 + 1] = v;
  }
  size_t written = 0;
  i2s_write(I2S_NUM_0, buf, sizeof(buf), &written, portMAX_DELAY);
}

void startSong1() {
  state = PLAYING_1;
  noteIdx = 0;
  noteStartMs = millis();
  phase = 0.0f;
}

void startSong2() {
  state = PLAYING_2;
  noteIdx = 0;
  noteStartMs = millis();
  phase = 0.0f;
}

void stopSong() {
  state = IDLE;
  noteIdx = 0;
  // 清掉 click 状态，避免误触发
  clickCount = 0;
  // 轻微静音输出，避免尾音
  for (int i = 0; i < 4; i++) playChunk(0);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BTN, INPUT_PULLUP);
  i2sInit();
  stopSong(); // 开机静音待机
}

void loop() {
  unsigned long now = millis();

  // ====== 播放状态：不响应按钮，播完就停 ======
  if (state == PLAYING_1 || state == PLAYING_2) {
    const Note* song = (state == PLAYING_1) ? song1 : song2;
    int len = (state == PLAYING_1) ? song1_len : song2_len;

    if (now - noteStartMs >= (unsigned long)song[noteIdx].ms) {
      noteIdx++;
      noteStartMs = now;
      if (noteIdx >= len) {
        stopSong();
        return;
      }
    }
    playChunk(song[noteIdx].f);
    return;
  }

  // ====== IDLE：检测单击/双击 ======
  bool btn = digitalRead(PIN_BTN);

  // 基础消抖：只处理“从 HIGH 到 LOW”的按下边沿
  if (btn != lastBtnRead) {
    lastChangeMs = now;
    lastBtnRead = btn;
  }

  // 当按钮稳定超过 DEBOUNCE_MS 且为 LOW，算一次“按下”
  static bool countedThisPress = false;
  if ((now - lastChangeMs) > DEBOUNCE_MS) {
    if (btn == LOW && !countedThisPress) {
      countedThisPress = true;

      // 记录 click
      if (clickCount == 0) {
        clickCount = 1;
        firstClickMs = now;
      } else if (clickCount == 1) {
        // 第二下在窗口内 -> 双击
        if (now - firstClickMs <= DOUBLE_CLICK_WINDOW_MS) {
          clickCount = 0;
          startSong2();
          return;
        }
      }
    }
    if (btn == HIGH) countedThisPress = false;
  }

  // 如果第一下之后超过窗口还没第二下 -> 认定为单击
  if (clickCount == 1 && (now - firstClickMs > DOUBLE_CLICK_WINDOW_MS)) {
    clickCount = 0;
    startSong1();
    return;
  }

  // 待机静音
  delay(5);
}
