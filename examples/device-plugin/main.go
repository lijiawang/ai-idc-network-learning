// A learning-only device plugin: two fake devices, no hardware access.
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

const (
	resourceName = "example.com/learning-device"
	socketName   = "learning-device.sock"
)

var deviceIDs = []string{"demo-0", "demo-1"}

type plugin struct {
	pluginapi.UnimplementedDevicePluginServer
}

// Kubelet calls this after registration to learn which optional RPCs are enabled.
func (*plugin) GetDevicePluginOptions(context.Context, *pluginapi.Empty) (*pluginapi.DevicePluginOptions, error) {
	return &pluginapi.DevicePluginOptions{}, nil
}

// Kubelet keeps this stream open. A real plugin sends again when health changes.
func (*plugin) ListAndWatch(_ *pluginapi.Empty, stream grpc.ServerStreamingServer[pluginapi.ListAndWatchResponse]) error {
	devices := make([]*pluginapi.Device, 0, len(deviceIDs))
	for _, id := range deviceIDs {
		devices = append(devices, &pluginapi.Device{ID: id, Health: pluginapi.Healthy})
	}
	if err := stream.Send(&pluginapi.ListAndWatchResponse{Devices: devices}); err != nil {
		return err
	}
	<-stream.Context().Done()
	return nil
}

// Kubelet has already selected IDs. Return a container environment variable
// so the chosen IDs are observable without any physical hardware.
func (*plugin) Allocate(_ context.Context, req *pluginapi.AllocateRequest) (*pluginapi.AllocateResponse, error) {
	response := &pluginapi.AllocateResponse{}
	for _, container := range req.ContainerRequests {
		for _, id := range container.DevicesIds {
			if id != "demo-0" && id != "demo-1" {
				return nil, fmt.Errorf("unknown device %q", id)
			}
		}
		log.Printf("Allocate: %v", container.DevicesIds)
		response.ContainerResponses = append(response.ContainerResponses, &pluginapi.ContainerAllocateResponse{
			Envs: map[string]string{"DEMO_DEVICE_IDS": strings.Join(container.DevicesIds, ",")},
		})
	}
	return response, nil
}

func register(ctx context.Context) error {
	callCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	conn, err := grpc.NewClient("unix://"+pluginapi.KubeletSocket, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return err
	}
	defer conn.Close()
	_, err = pluginapi.NewRegistrationClient(conn).Register(callCtx, &pluginapi.RegisterRequest{
		Version:      pluginapi.Version,
		Endpoint:     socketName,
		ResourceName: resourceName,
	})
	return err
}

func serve(ctx context.Context) error {
	socketPath := filepath.Join(pluginapi.DevicePluginPath, socketName)
	if err := os.Remove(socketPath); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	listener, err := net.Listen("unix", socketPath)
	if err != nil {
		return err
	}
	server := grpc.NewServer()
	pluginapi.RegisterDevicePluginServer(server, &plugin{})
	go func() {
		if err := server.Serve(listener); err != nil && !errors.Is(err, grpc.ErrServerStopped) {
			log.Printf("gRPC server stopped: %v", err)
		}
	}()
	defer server.Stop()
	defer listener.Close()

	// Our service must be listening before we register with kubelet.
	for {
		if err := register(ctx); err == nil {
			log.Printf("registered %s through %s", resourceName, pluginapi.KubeletSocket)
			break
		} else {
			log.Printf("register failed; retrying: %v", err)
		}
		if _, err := os.Stat(socketPath); errors.Is(err, os.ErrNotExist) {
			return err
		}
		select {
		case <-ctx.Done():
			return nil
		case <-time.After(2 * time.Second):
		}
	}

	// Kubelet removes device-plugin sockets on restart. Recreate ours and
	// register again when that happens.
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
			if _, err := os.Stat(socketPath); errors.Is(err, os.ErrNotExist) {
				log.Printf("socket removed; restarting plugin service")
				return err
			} else if err != nil {
				return err
			}
		}
	}
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	for ctx.Err() == nil {
		if err := serve(ctx); err != nil {
			log.Printf("service restarting: %v", err)
		}
	}
}
