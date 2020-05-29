//@ sm_output(output)
//@ sm_output(output2)


//@ sm_entry
pub fn entry(data : &[u8]) -> ResultMessage {
    authentic_execution::debug("entry");

    output(data);

    authentic_execution::success(None)
}

//@ sm_entry
pub fn entry2(data : &[u8]) -> ResultMessage {
    authentic_execution::debug("entry2");

    output2(data);

    authentic_execution::success(None)
}

//@ sm_entry
pub fn entry3(data : &[u8]) -> ResultMessage {
    authentic_execution::debug("entry3");

    output(data);
    output2(data);

    authentic_execution::success(None)
}
