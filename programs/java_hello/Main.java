public class Main {
    public static void main(String[] args) {
        if (args.length > 0) {
            // Join all arguments into a single string
            String message = String.join(" ", args);
            System.out.println("Hello, " + message + " from Java!");
        } else {
            System.out.println("Hello World from Java!");
        }
    }
}
