#include <sancus/reactive.h>

#include <stdio.h>

SM_OUTPUT(receiver, send_value);

SM_INPUT(receiver, data_requested, data, len) {
  puts("[receiver] requested data");
  send_value(NULL, 0);
}
