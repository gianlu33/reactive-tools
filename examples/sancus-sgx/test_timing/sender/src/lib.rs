use std::sync::Mutex;
use std::time::SystemTime;

lazy_static! {
    static ref START_TIME: Mutex<Option<SystemTime>> = {
        Mutex::new(None)
    };
}

//@ sm_output(request_data)

//@ sm_entry
pub fn test_timing(_data : &[u8]) -> ResultMessage {
    debug!("test_timing");

    let mut start_time = START_TIME.lock().unwrap();
    *start_time = Some(SystemTime::now());

    request_data(&[]);

    success(None)
}


//@ sm_input
pub fn data_received(data : &[u8]) {
    debug!("data_received");

    check_time_difference();
}


fn check_time_difference() {
    let start_time = START_TIME.lock().unwrap();

    match *start_time {
        Some(val)   => match SystemTime::now().duration_since(val) {
                Ok(n) => info!(&format!("RTT: {} ms", n.as_millis())),
                Err(_) => warning!("Error while checking the time difference"),
            },
        None        => warning!("No start time")
    }
}
