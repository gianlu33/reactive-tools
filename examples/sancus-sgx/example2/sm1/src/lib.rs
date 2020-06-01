//@ sm_output(get_value)
//@ sm_output(send_value)

//@ sm_input
pub fn recv_value(data : &[u8]) {
    info!("recv_value");

    if(data.len() < 2) {
        error!("Wrong data received");
        return;
    }

    let val = u16::from_le_bytes([data[0], data[1]]);

    debug!(&format!("Val: {}", val));

    send_value(data);
}


//@ sm_entry
pub fn request_values(data : &[u8]) -> ResultMessage {
    info!("request_values");

    get_value(&[]);

    success(None)
}
