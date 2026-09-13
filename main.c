/*
 * main.c - Valentine's Plant Heartbeat Display (BIG HEART VERSION)
 * STM32F446RE + ILI9341 2.8" LCD
 */

#include "main.h"
#include "ili9341.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

SPI_HandleTypeDef hspi1;
ADC_HandleTypeDef hadc1;
UART_HandleTypeDef huart2;

/* ==========================================
 * 布局配置 (Layout Configuration)
 * ========================================== */

/* 1. 标题位置 */
#define TITLE_Y_POS    10

/* 2. 爱心位置与大小 */
#define HEART_CENTER_X 120
#define HEART_CENTER_Y 90    // 稍微下移，给大爱心留空间
#define HEART_MIN_SCALE 2.2f // 基础大小 (原来是1.0)
#define HEART_MAX_SCALE 3.8f // 最大跳动大小 (原来是2.5)

/* 3. 文字位置 */
#define MSG_Y_POS      175   // 这里的文字必须大幅下移，否则会被大爱心遮住

/* 4. 波形图位置 */
#define WAVE_Y_CENTER  265   // 沉底显示
#define WAVE_HEIGHT    45    // 高度稍微压扁一点点，给上面腾空间
#define WAVE_WIDTH     240

static int16_t waveBuffer[WAVE_WIDTH];
static int waveIndex = 0;

/* Heart State */
static float heartScale = HEART_MIN_SCALE;
static float lastDrawnScale = 0.0f;

/* Messages */
static const char *messages[] = {
  "Feeling your love~",
  "Touch me gently...",
  "My heart beats for you",
  "Love is in the air",
  "You make me bloom!",
  "Be my Valentine <3",
  "Every touch is magic",
  "Growing with love",
  "You light me up!",
  "Sending love signals~"
};
#define NUM_MESSAGES 10
static int currentMessage = 0;
static uint32_t lastMessageChange = 0;

/* Signal */
#define ADC_MID 2048
static int signalSmooth = ADC_MID;

/* Colors (RGB565) */
#define CLR_BG       0x0000
#define CLR_HEART    0xF800 // Red
#define CLR_HPINK    0xFB56 // Pink
#define CLR_WAVE     0xF800
#define CLR_GRID     0x2000
#define CLR_GRIDMID  0x4000
#define CLR_TITLE    0xFEA0 // Gold
#define CLR_MSG      0xFDB8
#define CLR_LABEL    0x4000

/* Prototypes */
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_SPI1_Init(void);
static void MX_ADC1_Init(void);
static void MX_USART2_UART_Init(void);

/* ======================== HEART DRAWING ======================== */
static void drawFilledHeart(int cx, int cy, float scale, uint16_t color) {
  /* 增加绘制范围以适应更大的 Scale */
  for (int row = -20; row <= 20; row++) {
    float fy = (float)row;
    int minX = 999, maxX = -999;

    // 提高精度步长，防止大爱心出现这种空洞
    for (float t = 0; t < 6.28f; t += 0.01f) {
      float hx = 16.0f * sinf(t) * sinf(t) * sinf(t);
      float hy = -(13.0f * cosf(t) - 5.0f * cosf(2*t) - 2.0f * cosf(3*t) - cosf(4*t));

      if (fabsf(hy - fy) < 0.8f) { // 稍微放宽一点容差
        int px = (int)(hx * scale);
        if (px < minX) minX = px;
        if (px > maxX) maxX = px;
      }
    }
    if (minX < maxX)
      LCD_DrawHLine(cx + minX, cy + (int)(fy * scale), maxX - minX, color);
  }
}

static void drawHeartOutline(int cx, int cy, float scale, uint16_t color) {
  for (float t = 0; t < 6.28f; t += 0.02f) { // 步长加密，线条更连续
    float x = 16.0f * sinf(t) * sinf(t) * sinf(t);
    float y = -(13.0f * cosf(t) - 5.0f * cosf(2*t) - 2.0f * cosf(3*t) - cosf(4*t));
    int px = cx + (int)(x * scale);
    int py = cy + (int)(y * scale);
    if (px >= 0 && px < 240 && py >= 0 && py < 320) {
      LCD_DrawPixel(px, py, color);
      LCD_DrawPixel(px+1, py, color); // 加粗一点
    }
  }
}

static void updateHeartAnimation(int signal) {
  int deviation = abs(signal - ADC_MID);

  // 动态计算目标大小：基础大小 + 信号强度
  float target = HEART_MIN_SCALE + ((float)deviation / (float)ADC_MID) * 2.5f;

  // 限制最大最小范围
  if (target < HEART_MIN_SCALE) target = HEART_MIN_SCALE;
  if (target > HEART_MAX_SCALE) target = HEART_MAX_SCALE;

  // 平滑过渡
  heartScale += (target - heartScale) * 0.2f;

  // 只有变化足够大才重绘，避免闪烁
  if (fabsf(heartScale - lastDrawnScale) > 0.1f) {
    drawFilledHeart(HEART_CENTER_X, HEART_CENTER_Y, lastDrawnScale, CLR_BG); // 清除旧的
    drawFilledHeart(HEART_CENTER_X, HEART_CENTER_Y, heartScale, CLR_HEART);  // 画新的
    drawHeartOutline(HEART_CENTER_X, HEART_CENTER_Y, heartScale, CLR_HPINK);
    lastDrawnScale = heartScale;
  }
}

/* ======================== WAVEFORM ======================== */
static void drawWaveGrid(void) {
  for (int y = WAVE_Y_CENTER - WAVE_HEIGHT; y <= WAVE_Y_CENTER + WAVE_HEIGHT; y += 20)
    LCD_DrawHLine(0, y, 240, CLR_GRID);
  for (int x = 0; x < 240; x += 30)
    LCD_DrawVLine(x, WAVE_Y_CENTER - WAVE_HEIGHT, WAVE_HEIGHT * 2, CLR_GRID);
  LCD_DrawHLine(0, WAVE_Y_CENTER, 240, CLR_GRIDMID);
}

static void updateWaveform(int rawSignal) {
  int y = WAVE_Y_CENTER + WAVE_HEIGHT - (rawSignal * WAVE_HEIGHT * 2 / 4095);
  // Clip
  if (y < WAVE_Y_CENTER - WAVE_HEIGHT) y = WAVE_Y_CENTER - WAVE_HEIGHT;
  if (y > WAVE_Y_CENTER + WAVE_HEIGHT) y = WAVE_Y_CENTER + WAVE_HEIGHT;

  // Erase old pixel
  if (waveBuffer[waveIndex] != 0) {
    LCD_DrawPixel(waveIndex, waveBuffer[waveIndex], CLR_BG);
    LCD_DrawPixel(waveIndex, waveBuffer[waveIndex]-1, CLR_BG);
    LCD_DrawPixel(waveIndex, waveBuffer[waveIndex]+1, CLR_BG);
  }

  // Clear bar ahead
  int eraseAhead = (waveIndex + 5) % WAVE_WIDTH;
  LCD_DrawVLine(eraseAhead, WAVE_Y_CENTER - WAVE_HEIGHT, WAVE_HEIGHT * 2, CLR_BG);
  if (eraseAhead % 30 == 0)
    LCD_DrawVLine(eraseAhead, WAVE_Y_CENTER - WAVE_HEIGHT, WAVE_HEIGHT * 2, CLR_GRID);

  // Draw new pixel
  LCD_DrawPixel(waveIndex, y, CLR_WAVE);
  LCD_DrawPixel(waveIndex, y-1, CLR_WAVE);
  LCD_DrawPixel(waveIndex, y+1, CLR_WAVE);

  // Connect lines
  if (waveIndex > 0 && waveBuffer[waveIndex-1] != 0) {
    int prevY = waveBuffer[waveIndex-1];
    if (abs(y - prevY) > 1)
      LCD_DrawLine(waveIndex-1, prevY, waveIndex, y, CLR_WAVE);
  }

  waveBuffer[waveIndex] = y;
  waveIndex = (waveIndex + 1) % WAVE_WIDTH;
}

/* ======================== MESSAGES ======================== */
static void updateMessage(void) {
  uint32_t now = HAL_GetTick();
  if (now - lastMessageChange > 3000) {
    lastMessageChange = now;
    currentMessage = (currentMessage + 1) % NUM_MESSAGES;

    LCD_FillRect(0, MSG_Y_POS, 240, 20, CLR_BG);

    int len = strlen(messages[currentMessage]);
    int x = (240 - len * 6) / 2;
    LCD_DrawString(x, MSG_Y_POS, messages[currentMessage], CLR_MSG, CLR_BG, 1);
  }
}

static uint16_t readADC(void) {
  HAL_ADC_Start(&hadc1);
  HAL_ADC_PollForConversion(&hadc1, 10);
  uint16_t val = HAL_ADC_GetValue(&hadc1);
  HAL_ADC_Stop(&hadc1);
  return val;
}

/* ======================== MAIN ======================== */
int main(void)
{
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();
  MX_SPI1_Init();
  MX_ADC1_Init();
  MX_USART2_UART_Init();

  LCD_Init(&hspi1);
  LCD_SetRotation(0); // 确保你的 ili9341.c 已经修复了方向和颜色
  LCD_FillScreen(CLR_BG);

  memset(waveBuffer, 0, sizeof(waveBuffer));

  /* Static Elements */
  LCD_DrawString(45, TITLE_Y_POS, "~ Plant Love ~", CLR_TITLE, CLR_BG, 1);

  // Initial Heart Draw
  drawFilledHeart(HEART_CENTER_X, HEART_CENTER_Y, HEART_MIN_SCALE, CLR_HEART);
  drawHeartOutline(HEART_CENTER_X, HEART_CENTER_Y, HEART_MIN_SCALE, CLR_HPINK);
  lastDrawnScale = HEART_MIN_SCALE;

  // Initial Text
  LCD_DrawString(40, MSG_Y_POS, "Touch me gently...", CLR_MSG, CLR_BG, 1);

  // Grid
  drawWaveGrid();

  while (1)
  {
    uint16_t rawSignal = readADC();
    signalSmooth = (signalSmooth * 7 + (int)rawSignal * 3) / 10;

    updateWaveform(signalSmooth);
    updateHeartAnimation(signalSmooth);
    updateMessage();

    HAL_Delay(10);
  }
}

/* ======================== PERIPHERALS ======================== */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef o = {0};
  RCC_ClkInitTypeDef c = {0};
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);
  o.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  o.HSIState = RCC_HSI_ON;
  o.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  o.PLL.PLLState = RCC_PLL_ON;
  o.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  o.PLL.PLLM = 8; o.PLL.PLLN = 180;
  o.PLL.PLLP = RCC_PLLP_DIV2;
  o.PLL.PLLQ = 2; o.PLL.PLLR = 2;
  HAL_RCC_OscConfig(&o);
  HAL_PWREx_EnableOverDrive();
  c.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK|RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  c.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  c.AHBCLKDivider = RCC_SYSCLK_DIV1;
  c.APB1CLKDivider = RCC_HCLK_DIV4;
  c.APB2CLKDivider = RCC_HCLK_DIV2;
  HAL_RCC_ClockConfig(&c, FLASH_LATENCY_5);
}

static void MX_SPI1_Init(void)
{
  hspi1.Instance = SPI1;
  hspi1.Init.Mode = SPI_MODE_MASTER;
  hspi1.Init.Direction = SPI_DIRECTION_2LINES;
  hspi1.Init.DataSize = SPI_DATASIZE_8BIT;
  hspi1.Init.CLKPolarity = SPI_POLARITY_LOW;
  hspi1.Init.CLKPhase = SPI_PHASE_1EDGE;
  hspi1.Init.NSS = SPI_NSS_SOFT;
  hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_16;
  hspi1.Init.FirstBit = SPI_FIRSTBIT_MSB;
  hspi1.Init.TIMode = SPI_TIMODE_DISABLE;
  hspi1.Init.CRCCalculation = SPI_CRCCALCULATION_DISABLE;
  HAL_SPI_Init(&hspi1);
}

static void MX_ADC1_Init(void)
{
  ADC_ChannelConfTypeDef s = {0};
  hadc1.Instance = ADC1;
  hadc1.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
  hadc1.Init.Resolution = ADC_RESOLUTION_12B;
  hadc1.Init.ScanConvMode = DISABLE;
  hadc1.Init.ContinuousConvMode = DISABLE;
  hadc1.Init.DiscontinuousConvMode = DISABLE;
  hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
  hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc1.Init.NbrOfConversion = 1;
  hadc1.Init.DMAContinuousRequests = DISABLE;
  hadc1.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
  HAL_ADC_Init(&hadc1);
  s.Channel = ADC_CHANNEL_0; s.Rank = 1;
  s.SamplingTime = ADC_SAMPLETIME_84CYCLES;
  HAL_ADC_ConfigChannel(&hadc1, &s);
}

static void MX_USART2_UART_Init(void)
{
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  HAL_UART_Init(&huart2);
}

static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef g = {0};
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();

  g.Pin = GPIO_PIN_5 | GPIO_PIN_7;
  g.Mode = GPIO_MODE_AF_PP; g.Pull = GPIO_NOPULL;
  g.Speed = GPIO_SPEED_FREQ_VERY_HIGH; g.Alternate = GPIO_AF5_SPI1;
  HAL_GPIO_Init(GPIOA, &g);

  g.Pin = GPIO_PIN_9; g.Mode = GPIO_MODE_OUTPUT_PP;
  g.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &g);
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_9, GPIO_PIN_SET);

  g.Pin = GPIO_PIN_6; g.Mode = GPIO_MODE_OUTPUT_PP;
  HAL_GPIO_Init(GPIOB, &g);
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_6, GPIO_PIN_SET);

  g.Pin = GPIO_PIN_7; g.Mode = GPIO_MODE_OUTPUT_PP;
  HAL_GPIO_Init(GPIOC, &g);

  g.Pin = GPIO_PIN_0; g.Mode = GPIO_MODE_ANALOG; g.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(GPIOA, &g);

  g.Pin = GPIO_PIN_2 | GPIO_PIN_3;
  g.Mode = GPIO_MODE_AF_PP; g.Pull = GPIO_PULLUP;
  g.Speed = GPIO_SPEED_FREQ_VERY_HIGH; g.Alternate = GPIO_AF7_USART2;
  HAL_GPIO_Init(GPIOA, &g);

  __HAL_RCC_SPI1_CLK_ENABLE();
  __HAL_RCC_ADC1_CLK_ENABLE();
  __HAL_RCC_USART2_CLK_ENABLE();
}

void Error_Handler(void) { while(1) {} }
