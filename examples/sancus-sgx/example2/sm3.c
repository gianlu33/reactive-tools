#include <sancus/reactive.h>

#include <stdio.h>

SM_OUTPUT(sm3, send_value);

SM_INPUT(sm3, produce_value, data, len)
{
  puts("SM3 produce_value");

  unsigned int val = 33;

  send_value((unsigned char*) &val, sizeof(unsigned int));
}

SM_ENTRY(sm3) void init(uint8_t* input_data, size_t len)

{
    (void) input_data;
    (void) len;
     puts("hello from sm3");
}
