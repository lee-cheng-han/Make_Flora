#ifndef ILI9341_H
#define ILI9341_H

#include "stm32f4xx_hal.h"
#include <stdint.h>

#define LCD_CS_PORT   GPIOB
#define LCD_CS_PIN    GPIO_PIN_6
#define LCD_DC_PORT   GPIOC
#define LCD_DC_PIN    GPIO_PIN_7
#define LCD_RST_PORT  GPIOA
#define LCD_RST_PIN   GPIO_PIN_9

#define LCD_W  240
#define LCD_H  320

void LCD_Init(SPI_HandleTypeDef *hspi);
void LCD_FillScreen(uint16_t color);
void LCD_DrawPixel(int16_t x, int16_t y, uint16_t color);
void LCD_DrawLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color);
void LCD_DrawHLine(int16_t x, int16_t y, int16_t w, uint16_t color);
void LCD_DrawVLine(int16_t x, int16_t y, int16_t h, uint16_t color);
void LCD_FillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color);
void LCD_DrawRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color);
void LCD_DrawChar(int16_t x, int16_t y, char c, uint16_t color, uint16_t bg, uint8_t size);
void LCD_DrawString(int16_t x, int16_t y, const char *str, uint16_t color, uint16_t bg, uint8_t size);
void LCD_SetRotation(uint8_t r);

#endif
