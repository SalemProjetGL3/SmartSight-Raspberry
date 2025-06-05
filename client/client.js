/* 
1-make sure to install react-native-mqtt using:
npm install react-native-mqtt --save 
or
yarn add react-native-mqtt

2-Add Internet Permission (if not already present)
Ensure your Android app has permission to access the internet. Open your android/app/src/main/AndroidManifest.xml file and make sure this line is present,
usually above the <application> tag:
<uses-permission android:name="android.permission.INTERNET" />
It's typically there by default in new React Native projects.


*/
import React, { useState, useEffect, useRef } from 'react';
import { SafeAreaView, StyleSheet, Text, View, FlatList, AppState } from 'react-native';
import MQTT from 'react-native-mqtt';


// Configuration - Replace with your broker details and desired topic
const MQTT_BROKER_URI = 'tcp://IPV4Addr:1883'; // Use tcp for standard MQTT
const MQTT_TOPIC = 'vision/results'; // Topic to subscribe to
const MQTT_CLIENT_ID = `react_native_client_${Math.random().toString(16).substr(2, 8)}`;

const App = () => {
  const [messages, setMessages] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('Disconnected');
  const mqttClientRef = useRef(null);
  const appState = useRef(AppState.currentState);

  useEffect(() => {
    // Function to initialize and connect MQTT
    const connectMQTT = () => {
      if (mqttClientRef.current) {
        console.log('MQTT client already exists. Disconnecting before reconnecting.');
        mqttClientRef.current.disconnect();
      }

      console.log(`Attempting to connect to MQTT broker: ${MQTT_BROKER_URI} as ${MQTT_CLIENT_ID}`);
      setConnectionStatus('Connecting...');

      MQTT.createClient({
        uri: MQTT_BROKER_URI,
        clientId: MQTT_CLIENT_ID,
        // auth: true, // Set to true if you configured username/password
        // user: "your_username",
        // pass: "your_password",
        // tls: false, // Set to true if your broker uses SSL/TLS (probably doesn't lol)
      })
      .then(client => {
        mqttClientRef.current = client;

        client.on('closed', () => {
          console.log('MQTT: Connection closed');
          setConnectionStatus('Disconnected');
          // Optionally, attempt to reconnect here after a delay
          setTimeout(connectMQTT, 5000); // Reconnect after 5 seconds
        });

        client.on('error', (error) => {
          console.error('MQTT: Error:', error);
          setConnectionStatus(`Error: ${error.message || 'Unknown error'}`);
          client.disconnect(); // Ensure client is disconnected on critical error
        });

        client.on('message', (msg) => {
          console.log('MQTT: Message received:', msg);
          try {
            // Assuming the Python script sends JSON strings
            const parsedData = JSON.parse(msg.data);
            const displayMessage = `Topic: ${msg.topic}\nData: ${JSON.stringify(parsedData, null, 2)}`;
            setMessages(prevMessages => [
              { id: Math.random().toString(), text: displayMessage },
              ...prevMessages.slice(0, 49), // Keep last 50 messages
            ]);
          } catch (e) {
            console.warn("MQTT: Received non-JSON message or JSON parse error", msg.data);
            const displayMessage = `Topic: ${msg.topic}\nData: ${msg.data}`;
             setMessages(prevMessages => [
              { id: Math.random().toString(), text: displayMessage },
              ...prevMessages.slice(0, 49),
            ]);
          }
        });

        client.on('connect', () => {
          console.log('MQTT: Connected!');
          setConnectionStatus('Connected');
          console.log(`MQTT: Subscribing to topic: ${MQTT_TOPIC}`);
          client.subscribe(MQTT_TOPIC, 0); // QoS 0
        });

        client.connect();
      })
      .catch(err => {
        console.error('MQTT: createClient error', err);
        setConnectionStatus(`Failed to create client: ${err.message}`);
      });
    };

    connectMQTT(); // Initial connection attempt

    // Handle app state changes (e.g., app comes to foreground)
    const subscription = AppState.addEventListener('change', nextAppState => {
      if (
        appState.current.match(/inactive|background/) &&
        nextAppState === 'active'
      ) {
        console.log('App has come to the foreground! Reconnecting MQTT if necessary.');
        if (!mqttClientRef.current || !mqttClientRef.current.isConnected) {
           //connectMQTT(); // Re-initiate connection. Be careful with multiple client instances.
                           // A better approach might be to just call .connect() if client exists but is not connected.
                           // However, react-native-mqtt's `createClient` is the standard way to get a client instance.
                           // For robust reconnect logic, you might need a more complex state management.
        }
      }
      appState.current = nextAppState;
    });


    // Cleanup on component unmount
    return () => {
      console.log('MQTT: Cleaning up component');
      subscription.remove();
      if (mqttClientRef.current) {
        console.log('MQTT: Disconnecting client');
        mqttClientRef.current.disconnect();
        mqttClientRef.current = null;
      }
    };
  }, []); // Empty dependency array means this effect runs once on mount and cleanup on unmount

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>React Native MQTT Subscriber</Text>
        <Text style={styles.status}>Status: {connectionStatus}</Text>
        <Text style={styles.topic}>Subscribed to: {MQTT_TOPIC}</Text>
      </View>
      <FlatList
        style={styles.messageList}
        data={messages}
        renderItem={({ item }) => <Text style={styles.messageItem}>{item.text}</Text>}
        keyExtractor={item => item.id}
        inverted // To show newest messages at the bottom like a chat
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f0f0f0',
  },
  header: {
    padding: 15,
    backgroundColor: '#6200EE',
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    textAlign: 'center',
  },
  status: {
    fontSize: 14,
    color: '#eee',
    textAlign: 'center',
    marginTop: 4,
  },
  topic: {
    fontSize: 14,
    color: '#eee',
    textAlign: 'center',
    marginTop: 4,
  },
  messageList: {
    flex: 1,
    paddingHorizontal: 10,
  },
  messageItem: {
    padding: 10,
    marginTop: 5,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 5,
    fontSize: 12,
  },
});

export default App;