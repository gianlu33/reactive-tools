
//@ sm_input
pub fn input(_data : &[u8]) {
    authentic_execution::debug("input");
}

//@ sm_entry
pub fn entry(data : &[u8]) -> ResultMessage {
    authentic_execution::debug("entry");

    authentic_execution::success(None)
}
