#include <sancus/reactive.h>

#include <stdio.h>

SM_OUTPUT(receiver, send_value);

SM_INPUT(receiver, data_requested, data, len) {
  puts("[receiver] requested data");

  unsigned int value = 1;

  send_value((unsigned char *) &value, sizeof(value));
}
