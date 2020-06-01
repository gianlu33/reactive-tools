#include <sancus/reactive.h>

#include <stdio.h>

SM_OUTPUT(sm4, send_value);

SM_INPUT(sm4, produce_value, data, len)
{
  puts("SM4 produce_value");

  unsigned int val = 44;

  send_value((unsigned char*) &val, sizeof(unsigned int));
}

SM_ENTRY(sm4) void init(uint8_t* input_data, size_t len)

{
    (void) input_data;
    (void) len;
     puts("hello from sm4");
}
