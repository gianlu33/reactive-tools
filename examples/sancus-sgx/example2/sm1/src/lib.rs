//@ sm_output(get_value)
//@ sm_output(send_value)

//@ sm_input
pub fn recv_value(data : &[u8]) {
    authentic_execution::debug("recv_value");

    if(data.len() < 2) {
        authentic_execution::debug("Wrong data received");
    }

    let val = u16::from_le_bytes([data[0], data[1]]);

    authentic_execution::debug(&format!("Val: {}", val));

    send_value(data);
}


//@ sm_entry
pub fn request_values(data : &[u8]) -> ResultMessage {
    authentic_execution::debug("request_values");


    get_value(&[]);

    authentic_execution::success(None)
}
