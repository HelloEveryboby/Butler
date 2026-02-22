package bhl;

import java.util.Scanner;
import java.util.Map;
import java.util.HashMap;

public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        while (scanner.hasNextLine()) {
            String line = scanner.nextLine();
            if (line.contains("\"method\":\"to_xml\"")) {
                // Extremely simple manual parsing for demo
                String id = "unknown";
                if (line.contains("\"id\":\"")) {
                    int start = line.indexOf("\"id\":\"") + 6;
                    int end = line.indexOf("\"", start);
                    id = line.substring(start, end);
                }

                String xml = "<entry><key>id</key><value>" + id + "</value><engine>java-native</engine></entry>";
                System.out.println("{\"jsonrpc\":\"2.0\",\"result\":\"" + xml + "\",\"id\":null}");
            } else if (line.contains("\"method\":\"exit\"")) {
                break;
            }
        }
    }
}
