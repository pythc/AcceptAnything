fn double(value: i32) -> i32 { value * 2 }
fn main() { println!("{}", double(3)); }

#[cfg(test)]
mod tests {
    use super::double;
    #[test]
    fn doubles_input() { assert_eq!(double(3), 6); }
}
