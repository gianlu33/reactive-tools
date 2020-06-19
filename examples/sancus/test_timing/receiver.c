#include <sancus/reactive.h>

#include <stdio.h>

SM_INPUT(receiver, data_requested, data, len) {
  puts("[receiver] requested data");
}
