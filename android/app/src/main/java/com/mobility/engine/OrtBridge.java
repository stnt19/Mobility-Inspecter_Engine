package com.mobility.engine;

import ai.onnxruntime.*;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.Collections;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;

/** JNI transport only: all model policy, pixels, coordinates and NMS are Python. */
public final class OrtBridge implements AutoCloseable {
    private final OrtEnvironment env = OrtEnvironment.getEnvironment();
    private final OrtSession session;

    public OrtBridge(byte[] model) throws OrtException {
        try (OrtSession.SessionOptions options = new OrtSession.SessionOptions()) {
            options.setIntraOpNumThreads(2);
            session = env.createSession(model, options);
        }
    }

    private JSONArray metadata(Map<String, NodeInfo> nodes) throws Exception {
        JSONArray result = new JSONArray();
        for (Map.Entry<String, NodeInfo> row : nodes.entrySet()) {
            TensorInfo info = (TensorInfo) row.getValue().getInfo();
            JSONArray shape = new JSONArray();
            for (long n : info.getShape()) shape.put(n);
            result.put(new JSONObject().put("name", row.getKey()).put("shape", shape)
                .put("type", info.type == OnnxJavaType.FLOAT ? "tensor(float)" : info.type.toString()));
        }
        return result;
    }

    public String metadata() throws Exception {
        return new JSONObject().put("inputs", metadata(session.getInputInfo()))
            .put("outputs", metadata(session.getOutputInfo())).toString();
    }

    public byte[] run(byte[] pixels) throws Exception {
        String name = session.getInputNames().iterator().next();
        long[] shape = ((TensorInfo) session.getInputInfo().get(name).getInfo()).getShape();
        FloatBuffer values = ByteBuffer.wrap(pixels).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();
        try (OnnxTensor tensor = OnnxTensor.createTensor(env, values, shape);
             OrtSession.Result result = session.run(Collections.singletonMap(name, tensor))) {
            FloatBuffer output = ((OnnxTensor) result.get(0)).getFloatBuffer();
            ByteBuffer bytes = ByteBuffer.allocate(output.remaining() * 4).order(ByteOrder.LITTLE_ENDIAN);
            bytes.asFloatBuffer().put(output);
            return bytes.array();
        }
    }

    @Override public void close() throws OrtException { session.close(); }
}
