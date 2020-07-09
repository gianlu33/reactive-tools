//@ sm_output(send_output)

//@ sm_input
pub fn input_received(_data : &[u8]) {
    send_output(&[]);
}
