import java.util.*;
import java.io.*;

public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        while (scanner.hasNextLine()) {
            String line = scanner.nextLine();
            if (line.trim().isEmpty()) continue;
            processRequest(line);
        }
    }

    private static void processRequest(String line) {
        String method = getJsonValue(line, "method");
        String id = getJsonValue(line, "id");

        if (method.equals("to_xml_simple")) {
            String key = getJsonValue(line, "key");
            String value = getJsonValue(line, "value");
            String xml = String.format("<entry><key>%s</key><value>%s</value></entry>", key, value);
            System.out.println("{\"jsonrpc\":\"2.0\",\"result\":{\"xml\":\"" + xml + "\"},\"id\":\"" + id + "\"}");
        } else if (method.equals("exit")) {
            System.exit(0);
        } else {
            System.out.println("{\"jsonrpc\":\"2.0\",\"error\":{\"code\":-32601,\"message\":\"Method not found\"},\"id\":\"" + id + "\"}");
        }
    }

    private static String getJsonValue(String json, String key) {
        String searchKey = "\"" + key + "\"";
        int pos = json.indexOf(searchKey);
        if (pos == -1) return "";

        int afterKey = pos + searchKey.length();
        // Skip colon and spaces
        while (afterKey < json.length() && (json.charAt(afterKey) == ':' || Character.isWhitespace(json.charAt(afterKey)))) {
            afterKey++;
        }

        if (afterKey < json.length() && json.charAt(afterKey) == '\"') {
            afterKey++;
            int end = json.indexOf('\"', afterKey);
            return json.substring(afterKey, end);
        } else {
            int end = afterKey;
            while (end < json.length() && json.charAt(end) != ',' && json.charAt(end) != '}' && !Character.isWhitespace(json.charAt(end))) {
                end++;
            }
            return json.substring(afterKey, end);
        }
    }
}
