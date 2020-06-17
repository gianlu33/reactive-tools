#include <sancus/reactive.h>

#include <stdio.h>

#define TAP_OPEN 0x1 << 5
#define TAP_CLOSED 0

#include "/home/gianlu33/Desktop/thesis-main/authentic-execution/sancus/sancus-riot/sancus-testbed/reactive/pmodled.h"

static int SM_DATA(led_driver) initialized = 0;

SM_INPUT(led_driver, toggle_led, data, len) {
  puts("[led_driver] toggling led");

  if (len != 2) {
    puts("[led_driver] wrong data received");
  }

  if(!initialized) {
    pmodled_init();
  }

  puts("[led_driver] aaa");

  unsigned int state = *(unsigned int*) data;

  if (state) {
    pmodled_actuate(TAP_OPEN);
  }
  else {
    pmodled_actuate(TAP_CLOSED);
  }
}

// TODO remove this
void SM_ENTRY(led_driver) test_led(void)
{
    pmodled_init();
    pmodled_actuate(TAP_OPEN);
}
