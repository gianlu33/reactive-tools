#include <sancus/reactive.h>

#include <stdio.h>

static int SM_DATA(sm1) led_on = 0;

SM_OUTPUT(sm1, toggle_led);

SM_ENTRY(sm1) void init(uint8_t* input_data, size_t len)
{
    puts("Toggling led..");

    if (!led_on) {
      led_on = 1;
    }
    else {
      led_on = 0;
    }

    toggle_led((unsigned char*) &led_on, sizeof(unsigned int));
}
