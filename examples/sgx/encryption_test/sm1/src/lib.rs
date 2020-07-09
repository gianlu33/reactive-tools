use std::time::SystemTime;
use std::sync::Mutex;

lazy_static! {
    static ref START_TIME: Mutex<SystemTime> = {
        Mutex::new(SystemTime::now())
    };
}


//@ sm_output(send_output)

//@ sm_entry
pub fn start_test(_data : &[u8]) -> ResultMessage {
    debug!("starting test");

    let mut start_time = START_TIME.lock().unwrap();
    *start_time = SystemTime::now();

    send_output(&[]);

    success(None)
}

//@ sm_input
pub fn end_test(_data : &[u8]) {
    let start_time = START_TIME.lock().unwrap();

    match SystemTime::now().duration_since(*start_time) {
            Ok(n) => info!(&format!("RTT: {} ms", n.as_millis())),
            Err(_) => warning!("Error while checking the time difference")
    }
}
