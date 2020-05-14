
//@ sm_input
pub fn input2(data : &[u8]) {
    authentic_execution::debug("input");

    if(data.len() < 2) {
        authentic_execution::debug("Wrong data received");
    }

    let val = u16::from_le_bytes([data[0], data[1]]);

    authentic_execution::debug(&format!("Val: {}", val));
}

//@ sm_entry
pub fn entry(data : &[u8]) -> ResultMessage {
    authentic_execution::debug("entry");

    authentic_execution::success(None)
}
