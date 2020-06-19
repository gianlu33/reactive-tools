#include <sancus/reactive.h>

#include <stdio.h>

SM_OUTPUT(sender, request_data);

SM_ENTRY(sender) void test_timing(uint8_t* input_data, size_t len) {
    puts("[sender] start test");
    request_data(NULL, 0);
}
