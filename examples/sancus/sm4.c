#include <sancus/reactive.h>

#include <stdio.h>
#include <stdlib.h>

SM_OUTPUT(sm4, output);
SM_OUTPUT(sm4, output2);


SM_ENTRY(sm4) void init(uint8_t* input_data, size_t len)
{
     puts("SM4 init\n");

     unsigned int val = 33;

     output((unsigned char*) &val, sizeof(unsigned int));
}

SM_ENTRY(sm4) void init2(uint8_t* input_data, size_t len)
{
     puts("SM4 init2\n");

     unsigned int val = 33;

     output((unsigned char*) &val, sizeof(unsigned int));
     output2((unsigned char*) &val, sizeof(unsigned int));
}
