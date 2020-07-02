use std::net::TcpStream;
use reactive_net::{CommandCode, CommandMessage};
use std::time::SystemTime;

const SIZE : usize = 20;

//@ sm_entry
pub fn start_test(_data : &[u8]) -> ResultMessage {
    debug!("starting test");

    let start_time = SystemTime::now();

    if let Err(_) = ping_device() {
        return failure(ResultCode::InternalError, None);
    }

    match SystemTime::now().duration_since(start_time) {
            Ok(n) => info!(&format!("RTT: {} ms", n.as_millis())),
            Err(_) => {
                warning!("Error while checking the time difference");
                return failure(ResultCode::InternalError, None);
            }
    }

    success(None)
}

fn ping_device() -> Result<(), ()> {
    let mut stream = match TcpStream::connect("127.0.0.1:6000") {
        Ok(s) => s,
        Err(e)  => {
            error!(e);
            return Err(());
        }
    };

    debug!("Connected to SM");

    let payload = [0u8; SIZE];
    let cmd = CommandMessage::new(CommandCode::Ping, Some(payload.to_vec()));

    debug!(cmd);

    if let Err(e) = reactive_net::write_command(&mut stream, &cmd) {
        error!(e);
        return Err(());
    }

    match reactive_net::read_result(&mut stream) {
        Ok(_)   => debug!("Received result"),
        Err(e)  => {
            error!(e);
            return Err(());
        }
    };

    Ok(())
}
