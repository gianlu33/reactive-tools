use std::sync::Mutex;

lazy_static! {
    static ref VALUES: Mutex<Vec<u32>> = {
        Mutex::new(Vec::new())
    };
}

//@ sm_input
pub fn add_value(data : &[u8]) {
    info!("add_value");

    if data.len() < 2 {
        error!("Wrong data received");
        return;
    }

    let val = u16::from_le_bytes([data[0], data[1]]);

    let mut values = VALUES.lock().unwrap();

    values.push(val as u32);
}

//@ sm_entry
pub fn compute_sum(data : &[u8]) -> ResultMessage {
    info!("compute_sum");

    let mut values = VALUES.lock().unwrap();

    let sum : u32 = values.iter().sum();
    info!(&format!("Sum of numbers is {}", sum));

    success(None)
}
