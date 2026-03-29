curl https://ark.cn-beijing.volces.com/api/v3/responses \
-H "Authorization: Bearer <.env.doubao_api_key>" \
-H 'Content-Type: application/json' \
-d '{
    "model": "<.env.doubao_modle_id>",
    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/ark_demo_img_1.png"
                },
                {
                    "type": "input_text",
                    "text": "你看见了什么？"
                }
            ]
        }
    ]
}'