//@ sm_output(output)


//@ sm_entry
pub fn entry(data : &[u8]) -> ResultMessage {
    authentic_execution::debug("entry");

    output(data);

    authentic_execution::success(None)
}
